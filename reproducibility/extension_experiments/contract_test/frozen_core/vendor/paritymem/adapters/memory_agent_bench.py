"""MemoryAgentBench fallback replay for ordering and deterministic exact metrics.

MemoryAgentBench is not represented as a dynamic-action environment.  These
fixtures are explicitly synthetic no-model fixtures constructed through its
documented context -> ordered chunks -> ordered queries -> deterministic score
surface.  They are not claimed to reflect the natural data distribution.
"""

from __future__ import annotations

from copy import deepcopy
import re
import string
from typing import Any

from .common import build_fixture_trace


def _normalize(value: str) -> str:
    text = value.lower()
    text = "".join(character for character in text if character not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def _score(prediction: str, answer: str) -> dict[str, Any]:
    exact = _normalize(prediction) == _normalize(answer)
    substring = _normalize(answer) in _normalize(prediction)
    return {"exact_match": exact, "substring_exact_match": substring, "reward": int(exact)}


def build_memory_agent_bench_fixtures(commit: str, *, count: int = 100) -> tuple[list[Any], list[Any], dict[str, Any]]:
    official_bundles = []
    adapter_bundles = []
    for index in range(count):
        fixture_id = f"memory_agent_bench:synthetic:{index:03d}"
        context_id = f"context_{index:03d}"
        query_id = f"query_{index:03d}"
        chunks = [
            {"id": f"{context_id}:chunk:0", "kind": "memory_chunk", "value": f"Synthetic official-interface fact {index}."},
            {"id": f"{context_id}:chunk:1", "kind": "memory_chunk", "value": f"The deterministic answer token is value-{index}."},
        ]
        observation = [{"id": query_id, "kind": "query", "value": f"What is the deterministic answer token for item {index}?"}]
        # This benchmark has no action/tool menu; the answer surface is represented
        # as a single static answer action, not a fabricated dynamic menu.
        actions = [{"id": "ANSWER", "kind": "answer_schema", "parameters": {"text": "string"}}]
        aliases = {"ANSWER": "ANSWER"}
        answer = f"value-{index}"
        scorer_input = {"scorer_id": query_id, "task_id": query_id, "prediction": answer, "answer": answer}
        scorer_output = {"scorer_id": query_id, **_score(answer, answer)}
        state = {"context_id": context_id, "chunk_order": [chunk["id"] for chunk in chunks], "query_id": query_id}
        official_bundles.append(
            build_fixture_trace(
                benchmark="memory_agent_bench", commit=commit, fixture_id=fixture_id, task_id=query_id,
                step=index, observation_items=observation, action_items=actions, aliases=aliases,
                state_before=state, state_after=state, scorer_input=scorer_input, scorer_output=scorer_output,
                source_file="conversation_creator.py", source_function="get_chunks/get_query_and_answers",
                source_identifier=query_id, source_stage="official", memory_records=chunks, terminal=True,
            )
        )
        adapter_bundles.append(
            build_fixture_trace(
                benchmark="memory_agent_bench", commit=commit, fixture_id=fixture_id, task_id=query_id,
                step=index, observation_items=deepcopy(observation), action_items=deepcopy(actions), aliases=deepcopy(aliases),
                state_before=deepcopy(state), state_after=deepcopy(state), scorer_input=deepcopy(scorer_input),
                scorer_output=deepcopy(scorer_output), source_file="paritymem/adapters/memory_agent_bench.py",
                source_function="build_memory_agent_bench_fixtures", source_identifier=query_id,
                source_stage="adapter", memory_records=deepcopy(chunks), terminal=True,
            )
        )
    return official_bundles, adapter_bundles, {
        "fixture_count": count,
        "official_source_kind": "local_synthetic_no_model_fixture_from_official_interface",
        "natural_distribution_claim": False,
        "dynamic_action_menu_claim": False,
    }
