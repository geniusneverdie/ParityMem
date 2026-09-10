"""SGLang-equivalent, zero-model request preprocessing and admission.

The counter deliberately consumes the canonical JSON representation that will
cross the HTTP boundary.  It then reuses SGLang's installed Pydantic request
models and content-format normalizer before invoking the same Hugging Face
tokenizer/chat template arguments as ``OpenAIServingChat._apply_jinja_template``.
No model worker, HTTP service, generation, or post-hoc usage value is involved.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


FROZEN_SGLANG_VERSION = "0.5.6.post2"
FROZEN_SGLANG_SOURCE_SHA256 = {
    "sglang/srt/entrypoints/openai/serving_chat.py":
        "062262ee3f1faeaa26bc1a1756cdebecd9e2f602ea66fb6d7c648c4731c85cb3",
    "sglang/srt/entrypoints/openai/protocol.py":
        "06a514a23417a61872af36f8f81ea88cfff1ee05afb838d2caf374595982c59f",
    "sglang/srt/parser/jinja_template_utils.py":
        "febb4ba6b88c9a8768fad043f01f627eedc1b1915d6904020cf454a85dbaa488",
}


class ContractDriftError(RuntimeError):
    """The installed backend/tokenizer contract differs from the freeze."""


class SemanticMismatchError(RuntimeError):
    """Server preprocessing changed a request's semantic content."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_wire_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Round-trip the exact deterministic JSON representation sent by R3."""
    return json.loads(canonical_json_bytes(payload))


def _chat_template_bytes(template: Any) -> bytes:
    if isinstance(template, str):
        return template.encode("utf-8")
    return canonical_json_bytes(template)


def tokenizer_identity(
    tokenizer: Any,
    model_path: str | Path,
    *,
    model_revision: str,
    use_fast_requested: bool = True,
) -> dict[str, Any]:
    path = Path(model_path)
    file_hashes = {}
    for name in (
        "tokenizer_config.json",
        "tokenizer.json",
        "tokenizer.model",
        "special_tokens_map.json",
        "added_tokens.json",
        "config.json",
    ):
        candidate = path / name
        if candidate.is_file():
            file_hashes[name] = _sha256_file(candidate)
    template = tokenizer.chat_template
    return {
        "model_path": str(path.resolve()),
        "model_revision": model_revision,
        "tokenizer_class": type(tokenizer).__name__,
        "is_fast": bool(getattr(tokenizer, "is_fast", False)),
        "use_fast_requested": use_fast_requested,
        "file_sha256": file_hashes,
        "chat_template_sha256": _sha256_bytes(_chat_template_bytes(template)),
        "added_tokens": {
            str(index): str(token)
            for index, token in sorted(tokenizer.added_tokens_decoder.items())
        },
        "special_tokens_map": deepcopy(tokenizer.special_tokens_map),
        "all_special_ids": list(tokenizer.all_special_ids),
        "bos_token_id": tokenizer.bos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
        "padding_side": tokenizer.padding_side,
        "truncation_side": tokenizer.truncation_side,
        "model_max_length": tokenizer.model_max_length,
    }


def assert_tokenizer_identity(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    keys = (
        "model_revision",
        "tokenizer_class",
        "is_fast",
        "file_sha256",
        "chat_template_sha256",
        "added_tokens",
        "special_tokens_map",
    )
    differences = {
        key: {"expected": expected.get(key), "actual": actual.get(key)}
        for key in keys
        if actual.get(key) != expected.get(key)
    }
    if differences:
        raise ContractDriftError(
            "TOKENIZATION_CONTRACT_VERSION_DRIFT: "
            + json.dumps(differences, ensure_ascii=False, sort_keys=True)
        )


def verify_backend_identity(
    *,
    expected_version: str = FROZEN_SGLANG_VERSION,
    expected_sources: Mapping[str, str] = FROZEN_SGLANG_SOURCE_SHA256,
) -> dict[str, Any]:
    """Fail closed unless the installed SGLang preprocessing sources are frozen."""
    import sglang

    root = Path(sglang.__file__).resolve().parent.parent
    actual_version = str(getattr(sglang, "__version__", "UNKNOWN"))
    actual_sources = {
        relative: _sha256_file(root / relative) for relative in expected_sources
    }
    if actual_version != expected_version or actual_sources != dict(expected_sources):
        raise ContractDriftError(
            "TOKENIZATION_CONTRACT_VERSION_DRIFT: "
            + json.dumps(
                {
                    "expected_version": expected_version,
                    "actual_version": actual_version,
                    "expected_sources": dict(expected_sources),
                    "actual_sources": actual_sources,
                },
                sort_keys=True,
            )
        )
    return {
        "sglang_version": actual_version,
        "sglang_package_root": str(root),
        "source_sha256": actual_sources,
        "status": "PASS",
    }


def _server_messages_and_tools(
    wire_payload: dict[str, Any], *, verify_backend: bool
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]] | None, Any, Any]:
    if verify_backend:
        verify_backend_identity()

    from sglang.srt.entrypoints.openai.protocol import (
        ChatCompletionRequest,
        ToolChoice,
    )
    from sglang.srt.parser.jinja_template_utils import (
        detect_jinja_template_content_format,
        process_content_for_template_format,
    )

    request = ChatCompletionRequest.model_validate(wire_payload)
    processed_messages: list[dict[str, Any]] = []
    for message in request.messages:
        if message.content is None:
            message.content = ""
        message_dict = message.model_dump()
        processed_messages.append(message_dict)

    tools = None
    if request.tools and request.tool_choice != "none":
        if not isinstance(request.tool_choice, str):
            tools = [
                item.function.model_dump()
                for item in request.tools
                if item.function.name == request.tool_choice.function.name
            ]
        else:
            tools = [item.function.model_dump() for item in request.tools]

    return (
        request,
        processed_messages,
        tools,
        detect_jinja_template_content_format,
        process_content_for_template_format,
    )


def _special_token_positions(tokenizer: Any, token_ids: list[int]) -> list[dict[str, Any]]:
    special = set(tokenizer.all_special_ids)
    return [
        {
            "position": index,
            "token_id": token_id,
            "token": tokenizer.convert_ids_to_tokens(token_id),
        }
        for index, token_id in enumerate(token_ids)
        if token_id in special
    ]


def _semantic_tools_from_wire(wire_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in wire_payload.get("tools") or []:
        value = deepcopy(item.get("function", item))
        if value.get("strict") is False:
            value.pop("strict")
        result.append(value)
    tool_choice = wire_payload.get("tool_choice", "auto")
    if tool_choice == "none":
        return []
    if isinstance(tool_choice, dict):
        selected = (tool_choice.get("function") or {}).get("name")
        return [item for item in result if item.get("name") == selected]
    return result


def _semantic_tools_from_server(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result = []
    for item in tools or []:
        value = deepcopy(item)
        if value.get("strict") is False:
            value.pop("strict")
        result.append(value)
    return result


def assert_semantic_parity(
    wire_payload: Mapping[str, Any],
    server_messages: list[dict[str, Any]],
    server_tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    def without_none(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: without_none(item)
                for key, item in value.items()
                if item is not None
            }
        if isinstance(value, list):
            return [without_none(item) for item in value]
        return deepcopy(value)

    wire_messages = without_none(list(wire_payload["messages"]))
    normalized_server_messages = without_none(server_messages)
    message_pass = wire_messages == normalized_server_messages
    tool_pass = _semantic_tools_from_wire(wire_payload) == _semantic_tools_from_server(
        server_tools
    )
    if not message_pass or not tool_pass:
        raise SemanticMismatchError(
            "SERVER_PROMPT_SEMANTICS_MISMATCH: "
            + json.dumps(
                {"message_pass": message_pass, "tool_pass": tool_pass},
                sort_keys=True,
            )
        )
    return {
        "messages": "PASS",
        "tools": "PASS",
        "system": "PASS",
        "history": "PASS",
        "semantic_parity": "PASS",
    }


class ServerEquivalentCounter:
    """Offline counter bound to one frozen model/tokenizer contract."""

    def __init__(
        self,
        tokenizer: Any,
        *,
        model_path: str | Path,
        model_revision: str,
        expected_tokenizer_identity: Mapping[str, Any] | None = None,
        verify_backend: bool = True,
    ) -> None:
        self.tokenizer = tokenizer
        self.model_path = Path(model_path)
        self.model_revision = model_revision
        self.verify_backend = verify_backend
        self.identity = tokenizer_identity(
            tokenizer, self.model_path, model_revision=model_revision
        )
        if expected_tokenizer_identity is not None:
            assert_tokenizer_identity(self.identity, expected_tokenizer_identity)
        self.backend_identity = (
            verify_backend_identity() if verify_backend else {"status": "NOT_ENFORCED"}
        )

    def render(
        self,
        payload: Mapping[str, Any],
        *,
        include_text: bool = True,
        include_token_ids: bool = True,
    ) -> dict[str, Any]:
        wire_payload = canonical_wire_payload(payload)
        request, message_models, tools, detect_format, process_content = _server_messages_and_tools(
            wire_payload, verify_backend=False
        )
        content_format = detect_format(self.tokenizer.chat_template)
        messages = []
        for message in message_models:
            processed = process_content(message, content_format, [], [], [], [])
            if (
                processed["role"] == "assistant"
                and isinstance(processed.get("tool_calls"), list)
            ):
                for item in processed["tool_calls"]:
                    function = item.get("function") or {}
                    if isinstance(function.get("arguments"), str):
                        function["arguments"] = json.loads(function["arguments"])
            messages.append(processed)

        assistant_prefix = None
        if messages and messages[-1]["role"] == "assistant" and request.continue_final_message:
            assistant_prefix = messages[-1]["content"]
            messages = messages[:-1]

        template_kwargs = dict(request.chat_template_kwargs or {})
        apply_kwargs = {
            "tokenize": True,
            "add_generation_prompt": True,
            "tools": tools,
            "reasoning_effort": request.reasoning_effort,
            **template_kwargs,
        }
        fallback_used = False
        try:
            token_ids = self.tokenizer.apply_chat_template(messages, **apply_kwargs)
            rendered_text = (
                self.tokenizer.apply_chat_template(
                    messages, **{**apply_kwargs, "tokenize": False}
                )
                if include_text
                else None
            )
        except Exception:
            fallback_used = True
            fallback_tools = (
                [item if "function" in item else {"function": item} for item in tools]
                if tools
                else None
            )
            apply_kwargs["tools"] = fallback_tools
            token_ids = self.tokenizer.apply_chat_template(messages, **apply_kwargs)
            rendered_text = (
                self.tokenizer.apply_chat_template(
                    messages, **{**apply_kwargs, "tokenize": False}
                )
                if include_text
                else None
            )
            tools = fallback_tools

        token_ids = list(token_ids)
        if assistant_prefix:
            encoded = self.tokenizer.encode(assistant_prefix)
            if encoded and encoded[0] == self.tokenizer.bos_token_id:
                encoded = encoded[1:]
            token_ids += encoded
            if rendered_text is not None:
                rendered_text += self.tokenizer.decode(encoded)

        semantic = assert_semantic_parity(wire_payload, messages, tools)
        return {
            "rendered_text": rendered_text,
            "rendered_text_utf8_sha256": (
                _sha256_bytes(rendered_text.encode("utf-8"))
                if rendered_text is not None
                else None
            ),
            "token_ids": token_ids if include_token_ids else None,
            "token_count": len(token_ids),
            "special_token_positions": (
                _special_token_positions(self.tokenizer, token_ids)
                if include_token_ids
                else None
            ),
            "server_messages": messages,
            "server_tools": tools,
            "wire_request_sha256": _sha256_bytes(canonical_json_bytes(wire_payload) + b"\n"),
            "content_format": content_format,
            "add_generation_prompt": True,
            "add_special_tokens": False,
            "truncation": False,
            "padding": False,
            "chat_template_kwargs": template_kwargs,
            "reasoning_effort": request.reasoning_effort,
            "tool_choice": (
                request.tool_choice
                if isinstance(request.tool_choice, str)
                else request.tool_choice.model_dump()
            ),
            "fallback_tool_wrapper_used": fallback_used,
            "semantic_parity": semantic,
            "backend_identity": self.backend_identity,
            "tokenizer_identity": self.identity,
        }

    def count(self, payload: Mapping[str, Any]) -> int:
        return int(
            self.render(payload, include_text=False, include_token_ids=False)[
                "token_count"
            ]
        )

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
        max_output = int(
            payload.get("max_completion_tokens")
            or payload.get("max_tokens")
            or 0
        )
        required = count + max_output
        legacy_classification = "NOT_RECORDED"
        if legacy_client_count is not None:
            legacy_classification = (
                "CONSERVATIVE_CLIENT_OVERCOUNT"
                if legacy_client_count > count
                else (
                    "EXACT_PARITY"
                    if legacy_client_count == count
                    else "UNSAFE_CLIENT_UNDERCOUNT"
                )
            )
        safe = (
            required <= model_context_limit
            and required <= frozen_server_capacity
            and legacy_classification != "UNSAFE_CLIENT_UNDERCOUNT"
        )
        return {
            "model": payload.get("model"),
            "server_equivalent_offline_count": count,
            "legacy_client_count": legacy_client_count,
            "legacy_classification": legacy_classification,
            "requested_max_output_tokens": max_output,
            "required_context": required,
            "model_context_limit": model_context_limit,
            "frozen_server_capacity": frozen_server_capacity,
            "semantic_parity": "PASS",
            "capacity_safety": "PASS" if safe else "FAIL",
            "decision": "ADMISSION_PASS" if safe else "REQUEST_REJECTED_BEFORE_HTTP",
        }
