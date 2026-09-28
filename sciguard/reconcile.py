"""Cross-artifact numeric reconciliation (slot V) — the semantic slice of consistency (#3).

xref.py catches *mechanical* referencing errors (figure numbers, placeholders). This catches
*value* disagreements across artifacts: the same quantity reported differently in two places —
a mutant called "nearly inactive" in the text but plotted at ~10% in the SI, or two different m/z,
or two resolutions for one structure. It is
deterministic and key-based: it extracts (key → value) from each source and flags keys whose values
disagree beyond tolerance, plus the qualitative-vs-numeric contradiction (one source calls a mutant
"inactive" while another reports a non-trivial %). It does NOT do free-text entity resolution where
the key isn't a shared token (that still needs an LLM) — but mutant labels, m/z, resolutions, and
kinetic constants ARE canonical tokens, which is where the recurring disagreements live.

Pure stdlib; unit-testable.
"""
from __future__ import annotations

import re

_MUT = re.compile(r"\b([A-Z]\d{1,4}[A-Z])\b")           # K72A, D145N, …
# A one-letter-digits-one-letter token is also the formula of several common reagents, so the bare
# pattern above treats H2O and D2O as mutants and can then report a numeric_mismatch between two
# solvent percentages. Chemistry that merely looks like a mutant label is excluded by name.
_NOT_MUT = frozenset({"H2O", "D2O", "T2O", "H2S", "N2O", "D2S", "H2N", "O2N", "H2P", "O3S"})
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_QUAL_INACTIVE = re.compile(
    r"(?:nearly |almost |essentially |virtually )?(?:in|un)active"
    r"|no (?:detectable )?activity|abolished|loss of activity|dead|≈\s*0\b|~\s*0\b", re.I)


def extract_mutant_values(text: str, window: int = 70) -> dict:
    """Per mutant token: the %-values near it and whether it's described as inactive. The segment is
    clipped to the neighbouring mutant tokens so one mutant's number doesn't bleed onto another."""
    out: dict[str, dict] = {}
    ms = list(_MUT.finditer(text or ""))
    for i, m in enumerate(ms):
        mut = m.group(1)
        if mut.upper() in _NOT_MUT:
            continue
        end_next = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        # only the segment AFTER the mutant, clipped to the next mutant — the description follows the
        # mutant ("K72A … was nearly inactive"); a backward window bleeds the prior mutant's text.
        after = text[m.end():min(m.end() + window, end_next)]
        e = out.setdefault(mut, {"pct": [], "inactive": False})
        e["pct"] += [float(x) for x in _PCT.findall(after)]
        if _QUAL_INACTIVE.search(after):
            e["inactive"] = True
    return out


def reconcile_mutants(named_texts: dict, rel_tol: float = 0.25, qual_max: float = 5.0) -> dict:
    """Flag mutants whose %-values disagree across sources, or where one source says 'inactive'
    while another reports > qual_max %. named_texts = {source_name: text}."""
    maps = {src: extract_mutant_values(t) for src, t in named_texts.items()}
    muts = set().union(*[set(m) for m in maps.values()]) if maps else set()
    flags = []
    for mut in sorted(muts):
        vals = {src: m[mut]["pct"][0] for src, m in maps.items() if mut in m and m[mut]["pct"]}
        inact = {src for src, m in maps.items() if mut in m and m[mut]["inactive"]}
        if len(vals) >= 2:
            lo, hi = min(vals.values()), max(vals.values())
            if hi - lo > max(qual_max, rel_tol * max(hi, 1)):
                flags.append({"mutant": mut, "type": "numeric_mismatch", "values": vals})
                continue
        for src, v in vals.items():
            if v > qual_max and (inact - {src}):
                flags.append({"mutant": mut, "type": "qual_vs_numeric", "values": vals,
                              "called_inactive_by": sorted(inact - {src})})
                break
    return {"mutants_compared": len(muts), "flags": flags}


def extract_mz(text: str) -> list[float]:
    """All m/z values mentioned (for cross-checking EIC labels across SI drafts)."""
    return [float(x) for x in re.findall(r"m/z\s*[=:]?\s*(\d+(?:\.\d+)?)", text or "", re.I)]


def reconcile(named_maps: dict, rel_tol: float = 0.1, abs_tol: float = 0.0) -> list[dict]:
    """Generic keyed reconciliation. named_maps = {source: {key: value}}. Flag keys present in ≥2
    sources whose values disagree beyond both abs_tol and rel_tol (e.g. resolution, R_free, kcat)."""
    keys = set().union(*[set(m) for m in named_maps.values()]) if named_maps else set()
    flags = []
    for k in sorted(keys):
        vals = {s: m[k] for s, m in named_maps.items() if k in m}
        if len(vals) >= 2:
            lo, hi = min(vals.values()), max(vals.values())
            if (hi - lo) > abs_tol and (hi - lo) > rel_tol * max(abs(hi), abs(lo), 1e-9):
                flags.append({"key": k, "values": vals, "spread": round(hi - lo, 6)})
    return flags
