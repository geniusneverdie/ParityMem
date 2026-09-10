"""Conversation-history closure audit primitives for Gate H2B-H0."""

from .closure import (
    adapter_history,
    canonical_tool_calls,
    compare_roundtrip,
    direct_history,
    stable_hash,
)

__all__ = [
    "adapter_history",
    "canonical_tool_calls",
    "compare_roundtrip",
    "direct_history",
    "stable_hash",
]
