"""ContractIR-authoritative wrapper around the frozen SGLang offline counter.

The tokenizer and preprocessing path are identical to the T0 counter.  The
only changed authority is semantic comparison: wire JSON and SGLang's parsed
objects are compiled through the frozen benchmark BIC before comparison.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from paritymem.admission.server_equivalent_counter import (
    ServerEquivalentCounter,
    _server_messages_and_tools,
    _special_token_positions,
    canonical_wire_payload,
)
from paritymem.contract_ir.compiler import ContractCompiler, policy_from_bic
from paritymem.contract_ir.equivalence import compare_contract_ir
from paritymem.contract_ir.schema import SourceLayer


class ContractIRRuntimeMismatch(RuntimeError):
    """Server preprocessing changes semantic ContractIR."""


class ContractIRServerEquivalentCounter:
    """Preserve T0 counting while replacing strict type equality with P1."""

    def __init__(
        self,
        frozen_counter: ServerEquivalentCounter,
        *,
        bic_path: str | Path,
        preserve_model_generated_schema_events: bool = False,
    ) -> None:
        self.frozen_counter = frozen_counter
        self.tokenizer = frozen_counter.tokenizer
        self.identity = frozen_counter.identity
        self.backend_identity = frozen_counter.backend_identity
        self.compiler = ContractCompiler(
            policy_from_bic(bic_path),
            preserve_model_generated_schema_events=preserve_model_generated_schema_events,
        )
        self.preserve_model_generated_schema_events = bool(
            preserve_model_generated_schema_events
        )

    @staticmethod
    def _sha(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def render(
        self,
        payload: Mapping[str, Any],
        *,
        include_text: bool = True,
        include_token_ids: bool = True,
    ) -> dict[str, Any]:
        wire = canonical_wire_payload(payload)
        request, message_models, tools, detect_format, process_content = _server_messages_and_tools(
            wire, verify_backend=False
        )
        content_format = detect_format(self.tokenizer.chat_template)
        messages = []
        for message in message_models:
            processed = process_content(message, content_format, [], [], [], [])
            if processed["role"] == "assistant" and isinstance(processed.get("tool_calls"), list):
                for item in processed["tool_calls"]:
                    function = item.get("function") or {}
                    if isinstance(function.get("arguments"), str):
                        function["arguments"] = json.loads(function["arguments"])
            messages.append(processed)

        assistant_prefix = None
        if messages and messages[-1]["role"] == "assistant" and request.continue_final_message:
            assistant_prefix = messages[-1]["content"]
            messages = messages[:-1]

        kwargs = {
            "tokenize": True,
            "add_generation_prompt": True,
            "tools": tools,
            "reasoning_effort": request.reasoning_effort,
            **dict(request.chat_template_kwargs or {}),
        }
        fallback = False
        try:
            token_ids = self.tokenizer.apply_chat_template(messages, **kwargs)
            text = self.tokenizer.apply_chat_template(messages, **{**kwargs, "tokenize": False}) if include_text else None
        except Exception:
            fallback = True
            tools = [item if "function" in item else {"function": item} for item in tools] if tools else None
            kwargs["tools"] = tools
            token_ids = self.tokenizer.apply_chat_template(messages, **kwargs)
            text = self.tokenizer.apply_chat_template(messages, **{**kwargs, "tokenize": False}) if include_text else None
        token_ids = list(token_ids)
        if assistant_prefix:
            encoded = self.tokenizer.encode(assistant_prefix)
            if encoded and encoded[0] == self.tokenizer.bos_token_id:
                encoded = encoded[1:]
            token_ids += encoded
            if text is not None:
                text += self.tokenizer.decode(encoded)

        server_representation = deepcopy(wire)
        server_representation["messages"] = messages
        if tools is None:
            server_representation.pop("tools", None)
        else:
            server_representation["tools"] = tools
        wire_ir = self.compiler.compile(wire, source_layer=SourceLayer.OPENAI_WIRE)
        server_ir = self.compiler.compile(server_representation, source_layer=SourceLayer.SGLANG_INTERNAL)
        parity = compare_contract_ir(wire, server_representation, wire_ir, server_ir)
        if not parity.contract_ir_parity or wire_ir.ambiguous_fields or server_ir.ambiguous_fields:
            raise ContractIRRuntimeMismatch(
                "CONTRACT_IR_RUNTIME_MISMATCH: "
                + json.dumps(parity.to_dict(), ensure_ascii=False, sort_keys=True)
            )
        return {
            "rendered_text": text,
            "rendered_text_utf8_sha256": self._sha(text) if text is not None else None,
            "token_ids": token_ids if include_token_ids else None,
            "token_count": len(token_ids),
            "special_token_positions": _special_token_positions(self.tokenizer, token_ids) if include_token_ids else None,
            "server_messages": messages,
            "server_tools": tools,
            "wire_request_sha256": hashlib.sha256(json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n").hexdigest(),
            "wire_contract_ir_hash": wire_ir.semantic_hash(),
            "server_contract_ir_hash": server_ir.semantic_hash(),
            "P0_representation_parity": parity.representation_parity,
            "P1_contract_ir_parity": parity.contract_ir_parity,
            "classification": parity.classification,
            "semantic_differences": list(parity.semantic_differences),
            "content_format": content_format,
            "add_generation_prompt": True,
            "chat_template_kwargs": dict(request.chat_template_kwargs or {}),
            "fallback_tool_wrapper_used": fallback,
            "backend_identity": self.backend_identity,
            "tokenizer_identity": self.identity,
        }

    def count(self, payload: Mapping[str, Any]) -> int:
        return int(self.render(payload, include_text=False, include_token_ids=False)["token_count"])

    def admission_decision(
        self,
        payload: Mapping[str, Any],
        *,
        model_context_limit: int,
        frozen_server_capacity: int,
        legacy_client_count: int | None = None,
    ) -> dict[str, Any]:
        rendered = self.render(payload, include_text=False, include_token_ids=False)
        count = int(rendered["token_count"])
        maximum = int(payload.get("max_completion_tokens") or payload.get("max_tokens") or 0)
        required = count + maximum
        if legacy_client_count is None:
            legacy_classification = "NOT_RECORDED"
        elif legacy_client_count > count:
            legacy_classification = "CONSERVATIVE_CLIENT_OVERCOUNT"
        elif legacy_client_count == count:
            legacy_classification = "EXACT_PARITY"
        else:
            legacy_classification = "UNSAFE_CLIENT_UNDERCOUNT"
        passed = required <= model_context_limit and required <= frozen_server_capacity and legacy_classification != "UNSAFE_CLIENT_UNDERCOUNT"
        return {
            "decision": "ADMISSION_PASS" if passed else "REQUEST_REJECTED_BEFORE_HTTP",
            "server_equivalent_input_tokens": count,
            "requested_max_output_tokens": maximum,
            "required_context": required,
            "model_context_limit": model_context_limit,
            "frozen_server_capacity": frozen_server_capacity,
            "legacy_client_count": legacy_client_count,
            "legacy_classification": legacy_classification,
            "P1_contract_ir_parity": True,
            "wire_contract_ir_hash": rendered["wire_contract_ir_hash"],
            "server_contract_ir_hash": rendered["server_contract_ir_hash"],
        }
