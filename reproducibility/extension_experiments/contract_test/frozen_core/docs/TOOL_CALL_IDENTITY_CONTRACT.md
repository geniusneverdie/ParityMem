# Tool-Call Identity Contract

H1 distinguishes `TRANSPORT_CALL_ID`, `EXECUTION_CALL_ID`, `MODEL_VISIBLE_CALL_ID`, and `CANONICAL_ORDER_INDEX`. Transport IDs are frozen structured-API bookkeeping and audit provenance; they are not automatically model-visible semantic tokens. The Qwen and Llama templates render no call-ID literals. STATE executes, records results, and scores by canonical list order. Missing or duplicate required transport IDs and wrong call/result mappings remain hard failures.
