"""Source-of-record gate (#5) — a recorded claim must trace to the artifact it came from.

Backlog item #5 was a *rule* ("trace claims to source-of-record, not a downstream summary") with
nothing enforcing it. This makes it a GATE at RECORD: when a finding is committed to memory, it must
carry a `source`. Two failure modes are caught:

- **no source** → BLOCK: the finding is quarantined as a `gap` ("UNSOURCED CLAIM"), not stored as a
  trusted finding. (The lesson that produced this gate: MD/DFT numbers were cited from a draft's own
  summary instead of the collaborator's calculation file — an unsourced claim that looked sourced.)
- **a quantitative claim citing a DERIVED source** (manuscript draft / SI / summary / meeting report)
  rather than the PRIMARY source-of-record (raw data / calc doc / instrument file) → WARN.

`classify_source` tiers an artifact by type + filename hints; `require_source` is the pure gate;
`audit_memory` sweeps the store. Pure stdlib (reuses ingest.classify); unit-testable.
"""
from __future__ import annotations

import os
import re

from .ingest import classify as _classify_file

# filename hints (win over the bare file type)
_DERIVED_RE = re.compile(
    r"draft|manuscript|summary|まとめ|report|meeting|memo|note|presentation|slides?|review|\bSI\b",
    re.I)
_PRIMARY_RE = re.compile(
    r"raw|calc|measurement|spectr|chromatogram|kinetic|assay|standard.?curve|検量線|データ|"
    r"\bHPLC\b|\bMS\b|\bNMR\b", re.I)
_PRIMARY_CATS = {"sheet", "seq", "structure", "data"}   # ingest categories that are inherently primary
# A sealed, append-only lab-notebook entry is the strongest source there is, but every group numbers
# its entries differently. Override these two for your own scheme; the defaults match a generic
# "<PREFIX>-<number>" id and a filename that says it is a notebook or ledger.
LEDGER_ID = re.compile(r"^[A-Z]{1,6}-\d{1,6}$", re.I)
LEDGER_FILE_HINT = re.compile(r"ledger|lab.?notebook|\bELN\b", re.I)
_NUM = re.compile(r"\d")


def classify_source(src) -> tuple[str, str]:
    """Tier a source reference: 'primary' (source-of-record) / 'derived' (summary/draft) / 'none' / 'unknown'."""
    if not src or not str(src).strip():
        return ("none", "no source")
    s = str(src).strip()
    if LEDGER_ID.match(s) or LEDGER_FILE_HINT.search(s):
        return ("primary", "sealed lab-notebook entry (source-of-record)")
    name = os.path.basename(s)
    cat = _classify_file(name)
    if _PRIMARY_RE.search(name):
        return ("primary", f"name hints raw/calc data ({cat})")
    if _DERIVED_RE.search(name):
        return ("derived", f"name hints draft/summary ({cat})")
    if cat in _PRIMARY_CATS:
        return ("primary", f"{cat} file (raw data)")
    if cat in ("doc", "pdf", "slides"):
        return ("derived", f"{cat} prose (no raw-data hint)")
    if cat == "text":
        return ("primary", "text/data file")
    return ("unknown", f"unclassified ({cat})")


def require_source(item: dict) -> tuple[bool, str]:
    """The gate. (allowed, reason). Block a finding with no source; warn a numeric claim on a derived
    source. `item` = {text, source}."""
    src = item.get("source")
    if not src or not str(src).strip():
        return (False, "[BLOCKING] no source-of-record — a recorded finding must name the artifact "
                       "it came from (the raw data / calc doc / instrument file), not a summary")
    tier, why = classify_source(src)
    if _NUM.search(item.get("text", "") or "") and tier == "derived":
        return (True, f"[CHECK] quantitative claim cites a DERIVED source ({why}) — trace it to the "
                      f"primary data / source-of-record, not a draft or summary")
    return (True, f"sourced ({tier}: {why})")


def audit_memory(memory) -> dict:
    """Sweep a Memory store: findings missing a source, or quantitative findings on a derived source."""
    # An object with no .active() used to yield an empty finding list and therefore a PASSING audit —
    # so auditing None, or a plain list of findings, reported "ok". A gate that cannot fail is not a
    # gate, so the wrong type is now an error instead of a clean bill of health.
    if not hasattr(memory, "active"):
        raise TypeError(
            "audit_memory expects a store exposing .active(kind) -> list[dict]; got "
            f"{type(memory).__name__}. Pass your store, or wrap a plain list in one.")
    findings = memory.active("finding")
    unsourced, weak = [], []
    for it in findings:
        ok, why = require_source({"text": it.get("text", ""), "source": it.get("source")})
        if not ok:
            unsourced.append(it.get("text", "")[:80])
        elif "[CHECK]" in why:
            weak.append(it.get("text", "")[:80])
    return {"findings": len(findings), "unsourced": unsourced, "weak_source": weak,
            "ok": not unsourced}
