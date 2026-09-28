"""Cross-reference / placeholder auditor (slot V) — the deterministic core of cross-artifact consistency.

A manuscript review exposed a defect class this kind of harness rarely guards: an agent validates
WITHIN a dataset (dataproc) but not ACROSS artifacts. The single biggest recurring bug was figure
referencing — a figure numbered "4" in the deck but "5" in the text, the MD figure cited but absent
from the deck, unfilled placeholders ("Figure Sx", "PDB [ID]", "n = [3]"), and stale SI cross-refs
(text cites "Fig S21" after the SI was renumbered to S5).

This is the deterministic slice of that check: extract every Figure/Table/Scheme reference from the
text, find unfilled placeholders, and (given the figure set actually present) flag referenced-but-
missing and present-but-unreferenced items. It does NOT do semantic number-vs-number reconciliation
across docs (that needs an LLM pass) — it catches the mechanical referencing failures that a reviewer
sees first. Pure stdlib; unit-testable.
"""
from __future__ import annotations

import re

_REF = re.compile(r"\b(Fig(?:ure|\.)?|Table|Scheme)s?\.?\s*(S?\d{1,3}|Sx|XX|x)(?![\d])[A-Za-z]?\b", re.I)# unfilled placeholders: [ID]/[IDs]/[to be …]/[3]/[n]/n = [..]/Figure Sx/XX/LCxxxxxx/?? ???
# Accession placeholders arrive glued to a database prefix ("LCxxxxxx"), so a bounded `\bXX\b`
# never matches them: require a non-x prefix of 1-6 letters before >=4 x/X. That prefix guard
# refuses a pure x/X run, so an all-X stretch is not flagged — but a short-prefixed run ending
# at a word boundary (e.g. "MAXXXXXX") still matches; sequence text belongs elsewhere.# A bare run of >=2 question marks is a fill-me-in marker — an unwritten affiliation, an
# unwritten address — and is also what LaTeX prints for an undefined \ref. Never prose.
# It is worth flagging precisely because a reporting run can otherwise return zero blockers
# on a document that still has empty slots in its front matter.# Guard against real interrogatives (Latin "really??", or a CJK question ending in a kana/kanji): a
# genuine question mark follows a LETTER (Latin, kana U+3040-U+30FF, or Han U+4E00-U+9FFF), so the
# lookbehind refuses those. It also refuses a preceding `?`, which anchors the match at the START of
# the run — without it "really???" would still match at offset +1. Known accepted false-positive: an
# encoding-damaged extraction can turn glyphs into `?` runs; that is itself a defect worth surfacing
# on a manuscript about to be submitted, so it is not suppressed.
_PLACEHOLDER = re.compile(
    r"\[(?:ID|IDs|n|x|\d+|to be [^\]]*|PDB[^\]]*)\]"
    r"|\bn\s*=\s*\[[^\]]*\]"
    r"|\b(?:Fig(?:ure|\.)?)\s*(?:Sx|XX|x)\b"
    r"|\bSx\b|\bXX\b"
    r"|\b(?![Xx])[A-Za-z]{1,6}[Xx]{4,}\b"
    r"|(?<![A-Za-z?\uff1f\u3040-\u30ff\u4e00-\u9fff])[?\uff1f]{2,}", re.I)


def _norm(kind: str, num: str) -> str:
    k = kind.lower().rstrip(".")
    k = {"fig": "Figure", "figure": "Figure"}.get(k, kind.capitalize())
    return f"{k} {num.upper() if num.lower() in ('sx', 'xx', 'x') else num}"


def extract_refs(text: str) -> list[str]:
    """All Figure/Table/Scheme references in the text, normalised + de-duplicated, in order."""
    seen, out = set(), []
    for m in _REF.finditer(text or ""):
        ref = _norm(m.group(1), m.group(2))
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def audit_references(text: str, figure_labels: list[str] | None = None) -> dict:
    """Audit referencing integrity. With `figure_labels` (the figures actually present, e.g. from
    ingest.pptx_text), also flag referenced-but-missing and present-but-unreferenced figures."""
    refs = extract_refs(text)
    placeholders = sorted(set(re.sub(r"\s+", " ", p).strip() for p in _PLACEHOLDER.findall(text or "")
                              if isinstance(p, str)) | set(
        re.sub(r"\s+", " ", m.group(0)).strip() for m in _PLACEHOLDER.finditer(text or "")))
    out = {"referenced": refs, "placeholders": placeholders, "n_refs": len(refs)}
    if figure_labels is not None:
        present = {_canon(x) for x in figure_labels}
        ref_figs = {_canon(r) for r in refs if r.startswith(("Figure", "Fig"))}
        out["missing_figures"] = sorted(r for r in refs
                                        if r.startswith("Figure") and _canon(r) not in present)
        out["unreferenced_figures"] = sorted(x for x in figure_labels
                                             if _canon(x) not in ref_figs and "figure" in x.lower())
    return out


def _canon(s: str) -> str:
    """Canonical figure key: 'Fig. 4' / 'Figure 4' / 'figure4' → 'figure 4'."""
    m = re.search(r"(fig(?:ure|\.)?|table|scheme)\s*(s?\d+|sx|xx|x)", s, re.I)
    if not m:
        return s.strip().lower()
    k = "figure" if m.group(1).lower().startswith("fig") else m.group(1).lower()
    return f"{k} {m.group(2).lower()}"


def format_audit(a: dict) -> str:
    lines = [f"Reference audit — {a['n_refs']} refs"]
    if a.get("placeholders"):
        lines.append(f"  ⚠ UNFILLED PLACEHOLDERS ({len(a['placeholders'])}): {a['placeholders']}")
    if a.get("missing_figures"):
        lines.append(f"  ⚠ REFERENCED BUT NOT IN FIGURE SET: {a['missing_figures']}")
    if a.get("unreferenced_figures"):
        lines.append(f"  ⚠ IN FIGURE SET BUT NEVER REFERENCED: {a['unreferenced_figures']}")
    if not any(a.get(k) for k in ("placeholders", "missing_figures", "unreferenced_figures")):
        lines.append("  ok — no placeholders or figure-reference gaps")
    return "\n".join(lines)
