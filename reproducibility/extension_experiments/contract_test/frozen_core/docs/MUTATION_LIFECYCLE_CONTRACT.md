# Mutation Lifecycle Contract

Assignment is the pre-treatment arm. Opportunity is a score-independent event
matching the frozen target predicate. Materialization is execution of the
mutation operator. Exposure means the changed artifact becomes model-visible
or execution-visible. Effect is a downstream behavioral or scored difference.
None of these terms is interchangeable.

The lifecycle is UNASSIGNED -> ASSIGNED -> ARMED, followed by zero or more
opportunities. A path-conditional unit may end COMPLETED_WITHOUT_OPPORTUNITY.
An observed opportunity with no required materialization is
MISSED_MATERIALIZATION; too many are OVER_MATERIALIZATION. Both fail
infrastructure conformance. A clean unit may never materialize a mutation.

STATE M1 is available at the initial official action-menu epoch. STATE M4 is
path-conditional on the frozen target tool invocation. Its original strength is
one stale snapshot per unit: only the first opportunity materializes; later
opportunities are journaled and pass through. PM M1 and M4 use their frozen
Monday d1_s1 and d1_s4 steps and are always reached in the fixed week.
