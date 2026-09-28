"""artifactaudit — deterministic guardrails for AI-assisted research.

Two halves. Nothing here calls a model and nothing here opens a socket.

**integrity** — does this set of research artifacts actually hang together?
    `xref`        cross-artifact referencing plus unfilled placeholders ("Figure Sx", "[ID]", "n = [3]")
    `reconcile`   the same quantity reported differently in two places, incl. qualitative-vs-numeric
    `induction`   claim to evidence to strength to controls: catches overclaim and unbounded negatives
    `provenance`  a recorded finding must name its source of record, not a downstream summary
    `ingest`      inventory, text extraction and read coverage, so "I read the folder" is checkable

**confinement** — can a process work over unpublished data without that data leaving the machine?
    `egress`      host allowlist plus a URL scan of free text; `assert_airgap()` for a hard local mode
    `confidential` an unpublished-sequence registry: refuse to transmit *these*, allow everything else
    `sandbox/`    an OS-level companion (macOS Seatbelt profile) — the layer that actually holds

Every function in these seven modules is deterministic and covered by the test suite. The honest
limits of each check are stated in its own docstring and collected in the README, because a guardrail
that is weaker than advertised is worse than none.
"""
__all__ = ["xref", "reconcile", "induction", "provenance", "ingest", "egress", "confidential"]
__version__ = "0.1.0"
