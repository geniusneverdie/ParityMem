"""Source-grounded Benchmark Interface Contracts for Gate H0."""

from __future__ import annotations

from typing import Any

from paritymem.contracts.schema import (
    CAPABILITIES,
    BenchmarkInterfaceContract,
    Citation,
    ContractAssertion,
)


COMMITS = {
    "pm_bench": "e1093c470c8981daf522d4ef047a7c3a71e077d7",
    "state_bench": "5644b1838d96bc4483da29642d058ecaa6f80f7f",
    "memory_arena": "6cd9de14b71915e39ac742a20dc33785e14b6aab",
    "memory_agent_bench": "455306dcabc3842526eb83cd4e225e5d486c5c5d",
}

URLS = {
    "pm_bench": "https://github.com/genglinliu/PMBench.git",
    "state_bench": "https://github.com/microsoft/STATE-Bench.git",
    "memory_arena": "https://github.com/ZexueHe/MemoryArena.git",
    "memory_agent_bench": "https://github.com/HUST-AI-HYZ/MemoryAgentBench.git",
}


def _citation(benchmark: str, path: str, symbol: str, start: int, end: int, support: str = "code") -> Citation:
    return Citation(path, symbol, start, end, COMMITS[benchmark], support)


def _assertion(
    benchmark: str,
    field: str,
    semantics: str,
    raw_fields: list[str],
    citations: list[tuple[str, str, int, int, str | None]],
    *,
    confidence: str = "AUTHORITATIVE",
    limitations: list[str] | None = None,
) -> ContractAssertion:
    return ContractAssertion(
        field=field,
        semantics=semantics,
        raw_fields=raw_fields,
        citations=[_citation(benchmark, p, s, a, b, k or "code") for p, s, a, b, k in citations],
        confidence=confidence,
        limitations=list(limitations or []),
    )


def _caps(**enabled: bool) -> dict[str, bool]:
    return {capability: bool(enabled.get(capability, False)) for capability in CAPABILITIES}


def _pm_bench() -> BenchmarkInterfaceContract:
    b = "pm_bench"
    sections = {
        "session_contract": [
            _assertion(b, "day_session", "Each scenario day initializes task state, active-at-start tasks, stable day handles, and terminates after its ordered steps.", ["days", "tasks", "encoding", "steps"], [("sim/pm_bench.py", "run_interactive_day", 982, 1054, None)]),
        ],
        "observation_contract": [
            _assertion(b, "step_observation", "The agent sees step text, ordered options, the per-step action menu, query instructions, and clock only when visible by default.", ["text", "options", "time", "state_visibility"], [("sim/pm_bench.py", "run_interactive_day", 1079, 1099, None)]),
            _assertion(b, "visibility_boundary", "The internally computed due_now set is scorer/runtime state and is not part of the official observation contract.", ["due_now"], [("sim/pm_bench.py", "compute_due_now", 554, 593, None), ("sim/pm_bench.py", "run_interactive_day", 1070, 1099, None)]),
        ],
        "memory_contract": [
            _assertion(b, "state_query", "PM-Bench has no persistent agent-memory hook; query_state returns channel observations and maintains per-channel query cursors within the day.", ["state_events", "channel", "items", "last_query_step_by_channel"], [("sim/pm_bench.py", "resolve_state_query_items", 117, 183, None), ("sim/pm_bench.py", "run_interactive_day", 1052, 1129, None)]),
        ],
        "action_contract": [
            _assertion(b, "dynamic_action_menu", "Each step exposes active, not-completed tasks plus a deterministic sample of lures; cancelled tasks intentionally remain selectable.", ["handle", "id", "action_text"], [("sim/pm_bench.py", "build_step_action_menu", 649, 695, None)]),
            _assertion(b, "action_parser", "Actions are parsed as A/B/C plus task handles/IDs or state-channel queries and then deduplicated.", ["choice", "task_ids", "state_query_channel"], [("sim/pm_bench.py", "run_interactive_day", 1101, 1145, None)]),
        ],
        "transition_contract": [
            _assertion(b, "step_order", "Updates are applied, step-encoded tasks activated, due state computed, action resolved, then runtime completion is committed.", ["updates", "encoding", "choice", "task_ids"], [("sim/pm_bench.py", "run_interactive_day", 1054, 1145, None), ("sim/pm_bench.py", "apply_runtime_completions", 596, 646, None)]),
        ],
        "state_contract": [
            _assertion(b, "task_state", "Authoritative runtime task state tracks activation, completion, cancellation, cue observation, current updated fields, and result.", ["active", "completed", "canceled", "current", "result"], [("sim/pm_bench.py", "init_task_state", 279, 304, None), ("sim/pm_bench.py", "apply_task_update", 346, 382, None)]),
        ],
        "scorer_contract": [
            _assertion(b, "deterministic_set_scorer", "score_day rebuilds task state, applies the action log step-by-step, and computes TP/FP/FN, hit/late/miss, and violation metrics.", ["day", "actions", "task_ids", "set_tp", "set_fp", "set_fn"], [("sim/pm_bench.py", "score_day", 2266, 2583, None)]),
        ],
        "identifier_contract": [
            _assertion(b, "day_handle_mapping", "Task and lure IDs are mapped bijectively to stable-per-day anonymous task_N handles using a deterministic seeded shuffle.", ["id", "handle", "id_to_handle", "handle_to_id"], [("sim/pm_bench.py", "build_day_handle_maps", 529, 541, None)]),
        ],
        "ordering_contract": [
            _assertion(b, "menu_order", "Lure sampling and the final menu order are deterministic functions of day and step identifiers and are order-sensitive.", ["day", "step", "menu_entries"], [("sim/pm_bench.py", "build_step_action_menu", 678, 695, None)]),
        ],
        "side_effect_contract": [
            _assertion(b, "bounded_state_side_effects", "Only updates, state-query cursors, and validated selected task IDs mutate runtime state; scorer consumes the saved log separately.", ["updates", "last_query_step_by_channel", "task_ids"], [("sim/pm_bench.py", "run_interactive_day", 1052, 1145, None), ("sim/pm_bench.py", "score_log", 2586, 2652, None)]),
        ],
    }
    return BenchmarkInterfaceContract(
        benchmark_id=b,
        benchmark_version="frozen-main@e1093c4",
        upstream_commit=COMMITS[b],
        repository_url=URLS[b],
        capability_profile=_caps(
            HAS_DYNAMIC_ACTION_MENU=True,
            HAS_MUTABLE_ENVIRONMENT=True,
            HAS_DETERMINISTIC_SCORER=True,
            HAS_LURE_HANDLES=True,
        ),
        completeness="COMPLETE",
        sections=sections,
        selected_scope={"scenario": "data/synthetic_week_v9.json", "mode": "deterministic_no_model_step_replay"},
    )


def _state_bench() -> BenchmarkInterfaceContract:
    b = "state_bench"
    sections = {
        "session_contract": [
            _assertion(b, "task_run", "A task run deep-copies its task-local environment, opens with the task message, executes bounded agent/user turns, and emits a terminal trajectory.", ["task_id", "user_id", "opening_message", "max_agent_turns"], [("state_bench/orchestrator.py", "run_task", 125, 302, None)]),
        ],
        "observation_contract": [
            _assertion(b, "conversation_observation", "The canonical transcript begins with the opening user message and appends assistant/tool/user records in turn order.", ["conversation", "opening_message", "tool_calls"], [("state_bench/orchestrator.py", "run_task", 218, 269, None)]),
        ],
        "memory_contract": [
            _assertion(b, "agent_owned_memory_hook", "Agents may add read-only memory tools or inject a system memory message into turn input; neither may mutate the canonical benchmark transcript or state.", ["memory_tool_schemas", "memory_tool_handlers", "prepare_conversation", "ingest_trajectory"], [("state_bench/agents/base.py", "BaseAgent.memory_tool_schemas", 166, 210, None), ("state_bench/orchestrator.py", "_run_harness_executed_agent_turn", 76, 84, None)]),
        ],
        "action_contract": [
            _assertion(b, "static_tool_schema", "The action surface is the ordered concatenation of domain tool schemas and agent-declared memory tool schemas; undeclared tool names fail closed.", ["name", "arguments", "tools", "handlers"], [("state_bench/orchestrator.py", "_run_harness_executed_agent_turn", 66, 122, None)]),
        ],
        "transition_contract": [
            _assertion(b, "tool_transition", "The harness validates a requested tool name, calls exactly its registered handler, records arguments/result, and derives before/after state snapshots.", ["name", "arguments", "result", "db_before", "db_after"], [("state_bench/orchestrator.py", "_run_harness_executed_agent_turn", 97, 120, None), ("state_bench/orchestrator.py", "run_task", 215, 279, None)]),
        ],
        "state_contract": [
            _assertion(b, "authoritative_task_database", "The task-local environment snapshot is authoritative; StateDiff deterministically records created, modified, and deleted entities.", ["created", "modified", "deleted"], [("state_bench/schemas.py", "StateDiff.compute", 40, 86, None), ("state_bench/orchestrator.py", "run_task", 215, 279, None)]),
        ],
        "scorer_contract": [
            _assertion(b, "deterministic_final_state", "H0 parity uses only deterministic state-requirement evaluation reconstructed from the task environment and saved StateDiff; task/UX LLM judges are excluded.", ["state_requirements", "state_diff", "score"], [("state_bench/scoring.py", "evaluate_state_requirements", 97, 138, None), ("state_bench/scoring.py", "_reconstruct_final_snapshot", 405, 441, None)]),
        ],
        "identifier_contract": [
            _assertion(b, "task_and_entity_ids", "TaskDefinition.task_id identifies a run; scorer entity records are resolved by explicit per-entity primary-key mappings.", ["task_id", "record_key", "entity_type"], [("state_bench/schemas.py", "TaskDefinition", 133, 218, None), ("state_bench/scoring.py", "ENTITY_PRIMARY_KEY", 254, 337, None)]),
        ],
        "ordering_contract": [
            _assertion(b, "tool_and_turn_order", "Domain tools precede memory tools, requested calls execute in listed order, and the full stateless transcript is appended in turn order.", ["tools", "tool_calls", "conversation_full"], [("state_bench/orchestrator.py", "_run_harness_executed_agent_turn", 76, 120, None), ("state_bench/orchestrator.py", "run_task", 218, 269, None)]),
        ],
        "side_effect_contract": [
            _assertion(b, "task_local_isolation", "Each run receives a deep-copied task environment; memory retrieval is read-only and final state is captured as a diff before trajectory ingestion.", ["env_data", "deep_copy", "state_diff"], [("state_bench/orchestrator.py", "run_task", 159, 164, None), ("state_bench/orchestrator.py", "run_task", 274, 302, None), ("state_bench/agents/base.py", "BaseAgent.memory_tool_schemas", 166, 176, None)]),
        ],
    }
    return BenchmarkInterfaceContract(
        benchmark_id=b,
        benchmark_version="0.8.1",
        upstream_commit=COMMITS[b],
        repository_url=URLS[b],
        capability_profile=_caps(
            HAS_STATIC_TOOL_SCHEMA=True,
            HAS_MUTABLE_ENVIRONMENT=True,
            HAS_MEMORY_HOOK=True,
            HAS_DETERMINISTIC_SCORER=True,
            HAS_LLM_JUDGE=True,
            HAS_FINAL_STATE_SCORER=True,
        ),
        completeness="COMPLETE",
        sections=sections,
        selected_scope={"tasks": "first 100 official task/environment pairs in lexical order", "llm_judges": "excluded"},
    )


def _memory_arena() -> BenchmarkInterfaceContract:
    b = "memory_arena"
    sections: dict[str, list[ContractAssertion]] = {
        "session_contract": [_assertion(b, "preview_runner", "Domain runners create multi-step episodes, but the release is explicitly marked preview and depends on domain-specific services.", ["environment", "memory_system"], [("README.md", "release status", 1, 20, "documentation")], confidence="DOCUMENTED")],
        "observation_contract": [_assertion(b, "domain_observation", "Observation structure is domain-specific and returned by external/local environment wrappers.", ["observation"], [("env/env_systems/base_env.py", "BaseEnvironment.step", 5, 42, None)], confidence="INFERRED", limitations=["No single cross-domain deterministic observation fixture."])],
        "memory_contract": [_assertion(b, "external_memory_service", "Memory systems are selected through a wrapper and may require separate server/model dependencies.", ["memory_system"], [("memory/requirements.txt", "dependency declaration", 1, 13, "documentation")], confidence="DOCUMENTED")],
        "action_contract": [_assertion(b, "domain_action", "Action schemas vary by domain; no single resolved deterministic action contract is available in the preview release.", ["action"], [("env/env_systems/base_env.py", "BaseEnvironment.step", 5, 42, None)], confidence="UNRESOLVED")],
        "transition_contract": [_assertion(b, "step_signature_conflict", "The base environment and formal-reasoning implementation expose incompatible step-return arities, so deterministic cross-layer replay is unresolved.", ["observation", "reward", "done", "info"], [("env/env_systems/base_env.py", "BaseEnvironment.step", 5, 42, None), ("env/env_systems/math_env.py", "MathEnvironment.step", 113, 191, None)], confidence="UNRESOLVED")],
        "state_contract": [],
        "scorer_contract": [_assertion(b, "llm_judge_dependency", "The selected formal-reasoning domain delegates correctness judging to an LLM backend and is not a deterministic H0 scorer.", ["judge", "llm"], [("env/env_systems/math_env.py", "MathEnvironment.judge", 56, 90, None)], confidence="UNRESOLVED")],
        "identifier_contract": [],
        "ordering_contract": [],
        "side_effect_contract": [_assertion(b, "external_services", "Several domains require HTTP servers, API keys, remote datasets, or third-party runtime services.", ["api_key", "server"], [("README.md", "environment setup", 18, 39, "documentation")], confidence="DOCUMENTED")],
    }
    return BenchmarkInterfaceContract(
        benchmark_id=b,
        benchmark_version="preview-main@6cd9de1",
        upstream_commit=COMMITS[b],
        repository_url=URLS[b],
        capability_profile=_caps(
            HAS_MUTABLE_ENVIRONMENT=True,
            HAS_MEMORY_HOOK=True,
            HAS_MULTI_SESSION_STATE=True,
            HAS_LLM_JUDGE=True,
        ),
        completeness="BLOCKED",
        sections=sections,
        unresolved=[
            {"reason_code": "PREVIEW_CODE_INCOMPLETE", "scope": "cross-domain interface"},
            {"reason_code": "EXTERNAL_RUNTIME_BLOCKED", "scope": "environment and memory services"},
            {"reason_code": "SCORER_CONTRACT_UNRESOLVED", "scope": "formal reasoning LLM judge"},
        ],
        selected_scope={"attempted_domain": "formal_reasoning", "fallback_triggered": True},
    )


def _memory_agent_bench() -> BenchmarkInterfaceContract:
    b = "memory_agent_bench"
    sections = {
        "session_contract": [_assertion(b, "context_session", "Each context creates or reloads one agent memory instance, memorizes its ordered chunks, then processes all associated queries.", ["context_index", "context_chunks", "query_answer_pairs"], [("main.py", "process_context", 141, 166, None), ("initialization.py", "initialize_and_memorize_agent", 145, 172, None)])],
        "observation_contract": [_assertion(b, "formatted_query", "Dataset context is separated from non-context question fields; ordered questions and answers are formatted through a dataset/agent template.", ["context", "questions", "answers", "query"], [("conversation_creator.py", "_process_dataset_item", 118, 190, None)])],
        "memory_contract": [_assertion(b, "ordered_chunk_ingestion", "Each context is deterministically chunked in order and memorized before queries; an agent-specific saved folder scopes persistence.", ["context_chunks", "agent_save_folder"], [("conversation_creator.py", "get_chunks", 261, 290, None), ("initialization.py", "initialize_and_memorize_agent", 145, 172, None)])],
        "action_contract": [_assertion(b, "answer_only_surface", "The benchmark has no dynamic environment action menu; a query produces an answer string through AgentWrapper.send_message.", ["query", "output"], [("main.py", "process_single_query", 94, 101, None), ("agent.py", "AgentWrapper.send_message", 255, 279, None)])],
        "transition_contract": [_assertion(b, "query_progression", "Processing advances the global query index and durably saves results after every query; no mutable environment transition is defined.", ["query_index", "results"], [("main.py", "process_queries_for_context", 109, 138, None)])],
        "state_contract": [_assertion(b, "agent_memory_state", "Memory state is implementation-owned and scoped to an agent save folder per context; the benchmark itself does not define an authoritative mutable world state.", ["agent_save_folder", "context_index"], [("initialization.py", "generate_agent_save_folder", 121, 142, None), ("initialization.py", "initialize_and_memorize_agent", 145, 172, None)])],
        "scorer_contract": [_assertion(b, "deterministic_text_metrics", "For supported H0 tasks, answers are normalized then scored by exact and substring-exact match; LLM-judged LongMemEval/InfBench branches are excluded.", ["prediction", "answer", "exact_match", "substring_exact_match"], [("utils/eval_other_utils.py", "normalize_answer/drqa_exact_match_score/substring_exact_match_score", 32, 116, None), ("utils/eval_other_utils.py", "post_process", 450, 476, None)])],
        "identifier_contract": [_assertion(b, "query_identifiers", "Global query_index and optional qa_pair_id are preserved in result records and resume mapping.", ["query_id", "qa_pair_id", "context_index"], [("main.py", "process_queries_for_context", 109, 138, None), ("initialization.py", "load_existing_results", 63, 118, None)])],
        "ordering_contract": [_assertion(b, "context_chunk_query_order", "Contexts, chunks, and query-answer pairs preserve list order; processing is context-major then query-major.", ["contexts", "chunks", "query_and_answers"], [("conversation_creator.py", "get_chunks/get_query_and_answers", 261, 318, None), ("main.py", "main", 186, 201, None)])],
        "side_effect_contract": [_assertion(b, "saved_memory_and_results", "The harness writes agent state per context and overwrites the result JSON after each query; it has no benchmark environment database mutation.", ["agent_save_folder", "output_path"], [("initialization.py", "initialize_and_memorize_agent", 145, 172, None), ("main.py", "save_results_to_file", 65, 91, None)])],
    }
    return BenchmarkInterfaceContract(
        benchmark_id=b,
        benchmark_version="frozen-main@455306d",
        upstream_commit=COMMITS[b],
        repository_url=URLS[b],
        capability_profile=_caps(
            HAS_MEMORY_HOOK=True,
            HAS_MULTI_SESSION_STATE=True,
            HAS_DETERMINISTIC_SCORER=True,
            HAS_LLM_JUDGE=True,
        ),
        completeness="COMPLETE",
        sections=sections,
        selected_scope={
            "contract_scope": ["observation", "memory", "ordering", "identifier", "deterministic exact/substring scorer"],
            "dynamic_action_environment": False,
            "llm_judged_datasets": "excluded",
        },
    )


def build_contracts() -> dict[str, BenchmarkInterfaceContract]:
    contracts = {
        "pm_bench": _pm_bench(),
        "state_bench": _state_bench(),
        "memory_arena": _memory_arena(),
        "memory_agent_bench": _memory_agent_bench(),
    }
    for contract in contracts.values():
        contract.validate()
    return contracts
