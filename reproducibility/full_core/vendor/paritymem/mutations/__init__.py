"""Controlled interface distortion operators."""

from .lifecycle import (
    LifecycleInvariantError,
    MutationLifecycleJournal,
    MutationLifecycleStatus,
    MutationSpec,
    RecoveryDisposition,
    count_opportunities,
    event_is_opportunity,
)
from .operators import MUTATION_CLASSES, apply_mutation

__all__ = [
    "LifecycleInvariantError",
    "MUTATION_CLASSES",
    "MutationLifecycleJournal",
    "MutationLifecycleStatus",
    "MutationSpec",
    "RecoveryDisposition",
    "apply_mutation",
    "count_opportunities",
    "event_is_opportunity",
]
