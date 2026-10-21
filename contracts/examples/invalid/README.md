# Invalid fixtures

Each file isolates one authority or workflow violation. Package validation must
reject every listed fixture.

| Fixture | Expected rejection |
|---|---|
| `action-descriptor-cross-family.invalid.json` | A descriptor for one action family cannot carry command fields reserved for another family. |
| `authority-replay-existing-evidence-reset.invalid.json` | A complete initial evidence projection cannot reset a subject already present at the authoritative checkpoint. |
| `authority-event-alignment-missing-prior-state.invalid.json` | A state-dependent alignment update must bind the immediately prior subject state. |
| `authority-event-cross-family.invalid.json` | An alignment event cannot also change research attention. |
| `authority-event-evidence-reclassification-missing-prior-state.invalid.json` | A noninitial evidence reclassification must bind the immediately prior subject state. |
| `catalog-assessment-unknown-modification-target.invalid.json` | A modification option must name one of the run's actual proposals in applies_to. |
| `decision-auto-action.invalid.json` | A displayed action cannot authorize automatic execution. |
| `method-lifecycle-malformed-digest.invalid.json` | A command digest must be exactly 64 lowercase hexadecimal characters. |
| `method-lifecycle-no-op.invalid.json` | A lifecycle command must change active to retired or retired to active. |
| `method-proposal-missing-profile.invalid.json` | A method proposal must author its computational_profile. |
| `record-state-old-method-included.invalid.json` | Evidence from an older method version must be excluded and outdated, not included as exact current evidence. |
| `run-cancellation-submitted.invalid.json` | A cancellation command cannot target a run whose immutable submission already exists. |
| `run-manifest-current-only-history.invalid.json` | A current-only manifest cannot include selected history. |
| `run-state-cancellation-after-submission.invalid.json` | A run cannot transition from submitted back to cancellation requested. |
| `scientific-record-mutable-position.invalid.json` | Immutable scientific content cannot contain derived record position. |

These fixtures test typed action isolation, digest shape, cancellation,
authorization, lifecycle, event-family, immutable-content, and derived-state
boundaries. They do not test scientific truth.
