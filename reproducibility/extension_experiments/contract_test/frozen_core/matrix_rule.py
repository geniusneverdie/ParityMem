"""Verbatim isolated original matrix prediction function; no preparation side effects."""

def prediction(model: str, backend: str, projection: dict) -> dict:
    count = len(projection["native_calls"])
    mixed = bool(projection["assistant_content"].strip())
    if model == "Llama" and count > 1:
        return {"predicted_class": "BLOCKING_NON_CLOSURE", "predicted_reachability": "BLOCKED",
                "predicted_first_divergence": "Llama template multi-tool cardinality guard",
                "predicted_contract_layer": "conversation-history closure", "predicted_severity": "R3"}
    if model == "Mistral" and backend == "SGLang":
        return {"predicted_class": "PAIRING_FAILURE", "predicted_reachability": "BLOCKED",
                "predicted_first_divergence": "SGLang generated 29-character tool-call ID versus Mistral 9-character ID guard",
                "predicted_contract_layer": "identifier domain / history closure", "predicted_severity": "R3"}
    if model == "Mistral" and mixed:
        return {"predicted_class": "R2_SEMANTIC_ALTERATION", "predicted_reachability": "REACHABLE",
                "predicted_first_divergence": "Mistral tool-call template branch omits assistant text",
                "predicted_contract_layer": "model-visible semantic history", "predicted_severity": "R2"}
    return {"predicted_class": "SAFE_REACHABLE", "predicted_reachability": "REACHABLE",
            "predicted_first_divergence": "NONE", "predicted_contract_layer": "NONE", "predicted_severity": "R0"}
