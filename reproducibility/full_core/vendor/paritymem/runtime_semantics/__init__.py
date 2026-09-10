"""Ownership-aware model-output boundaries and durable environment transitions."""

from .model_output import (
    ContractOwnership,
    ModelOutputClassification,
    ModelOutputIR,
    OfficialValidationStatus,
    build_model_output_ir,
    materialize_dynamic_history,
)
from .transition_journal import (
    EnvironmentTransitionJournal,
    JournalInvariantError,
    RecoveryDisposition,
    TransitionStatus,
)

__all__ = [
    "ContractOwnership",
    "ModelOutputClassification",
    "ModelOutputIR",
    "OfficialValidationStatus",
    "build_model_output_ir",
    "materialize_dynamic_history",
    "EnvironmentTransitionJournal",
    "JournalInvariantError",
    "RecoveryDisposition",
    "TransitionStatus",
]
