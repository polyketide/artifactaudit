"""Induction audit (slot V) — the deterministic backstop for stage 5 (归纳, results → claims).

`results-synthesis` (the skill) makes the inductive jump from data to claims; this is the *computational*
sensor that the stage lacked. It does NOT invent or judge the science — it checks that the claim map the
synthesis stage emits obeys the rules the skill itself states, so an overclaim can't pass silently:

  1. every claim is backed by ≥1 piece of evidence (a data id / sensor / artifact)           → `no_evidence`
  2. a STRONG claim (demonstrates/establishes/proves) lists its controls …                    → `overclaim_no_controls`
     … and does NOT rest on a sensor that TRIPPED at stage 4 (mass balance off, n<3, …)        → `overclaim_tripped_sensor`
  3. a NEGATIVE claim ("no product / inactive") is LOD/LOQ-bounded, not a clean zero           → `negative_not_lod_bounded`
  4. a HEADLINE claim has been retrieval-checked against the literature                        → `headline_not_retrieval_checked`

The verb→strength ladder mirrors `results-synthesis` / `chem-writing`: overclaim is the default failure
mode, so an un-annotated claim is rated by its verb. Pure stdlib; deterministic; unit-testable. The
calibration case is a real '"nearly inactive" in the text, ~10% in the SI' overclaim — a strong claim
whose control/sensor evidence didn't carry the verb.
"""
from __future__ import annotations

import re

# Verb → strength ladder (lower-cased substring match on the claim text when `strength` isn't given).
STRONG = ("demonstrate", "establish", "prove", "confirm", "show that", "reveals that", "definitively")
MODERATE = ("suggest", "consistent with", "indicate", "support", "imply", "is in line with")
WEAK = ("hint", "cannot yet distinguish", "cannot rule out", "may ", "might ", "could ", "appears")

_NEG = re.compile(r"\bno (?:detectable )?(?:product|activity|conversion|turnover)\b"
                  r"|\b(?:in|un)active\b|\bnot detected\b|\babolished\b|\bloss of activity\b", re.I)


def claim_strength(text: str, explicit: str | None = None) -> str:
    """Rate a claim 'strong' / 'moderate' / 'weak'. Explicit annotation wins; else infer from the verb.

    Default is 'strong' when a strong verb is present, otherwise 'moderate' — overclaim is the failure
    mode we guard, so an unmarked claim is NOT charitably downgraded to weak."""
    if explicit:
        e = explicit.strip().lower()
        if e in ("strong", "demonstrates", "establishes", "proves"):
            return "strong"
        if e in ("weak", "hints", "tentative"):
            return "weak"
        if e in ("moderate", "suggests", "indicates"):
            return "moderate"
    t = (text or "").lower()
    if any(w in t for w in STRONG):
        return "strong"
    if any(w in t for w in WEAK):
        return "weak"
    if any(w in t for w in MODERATE):
        return "moderate"
    return "moderate"


def is_negative(claim: dict) -> bool:
    """A claim asserting absence (no product / inactive) — must be LOD-bounded, not a clean zero."""
    if claim.get("negative") is not None:
        return bool(claim["negative"])
    return bool(_NEG.search(claim.get("text", "")))


def audit_claims(claims: list[dict], *, tripped_sensors: set[str] | list[str] | None = None) -> dict:
    """Audit a claim–evidence–strength–caveat map. Returns {n_claims, n_strong, flags, ok}.

    Each claim dict (as emitted by `results-synthesis`):
      text (str, required), strength (opt: strong/moderate/weak), evidence (list of data-id/sensor),
      controls (list), negative (opt bool), lod_bounded (opt bool), headline (opt bool),
      retrieval_checked (opt bool). `tripped_sensors` = stage-4 sensor keys that flagged a problem.
    """
    tripped = set(tripped_sensors or ())
    flags: list[dict] = []
    n_strong = 0
    for c in claims or []:
        text = (c.get("text") or "").strip()
        strength = claim_strength(text, c.get("strength"))
        evidence = list(c.get("evidence") or [])
        controls = list(c.get("controls") or [])
        if strength == "strong":
            n_strong += 1

        # 1. evidence present
        if not evidence:
            flags.append({"claim": text, "type": "no_evidence",
                          "detail": "claim carries no data id / sensor / artifact"})

        # 2. strong-claim discipline: controls listed + no tripped sensor underneath it
        if strength == "strong":
            if not controls:
                flags.append({"claim": text, "type": "overclaim_no_controls",
                              "detail": "strong verb but no controls listed to rule out alternatives"})
            rests_on_tripped = sorted(set(evidence) & tripped) or (["<tripped>"] if c.get("tripped") else [])
            if rests_on_tripped:
                flags.append({"claim": text, "type": "overclaim_tripped_sensor",
                              "detail": f"strong claim rests on a tripped sensor: {rests_on_tripped}"})

        # 3. negative claims must be LOD-bounded
        if is_negative(c) and not c.get("lod_bounded"):
            flags.append({"claim": text, "type": "negative_not_lod_bounded",
                          "detail": "absence claim not bounded by LOD/LOQ (a clean zero is not evidence)"})

        # 4. headline claims must be retrieval-checked
        if c.get("headline") and not c.get("retrieval_checked"):
            flags.append({"claim": text, "type": "headline_not_retrieval_checked",
                          "detail": "headline claim not checked against the literature (confirm/extend/contradict?)"})

    return {"n_claims": len(claims or []), "n_strong": n_strong, "flags": flags, "ok": not flags}


# --- pre-parser: split a paragraph into candidate claim records (feeds audit_claims) ----------

# Citation / evidence token patterns the agent would otherwise eyeball. stdlib regex only.
_CITE_PATTERNS = [
    ("figure", re.compile(r"\bFig(?:ure)?s?\.?\s*S?\d+[A-Za-z]?\b", re.I)),
    ("table", re.compile(r"\bTables?\s*S?\d+[A-Za-z]?\b", re.I)),
    ("scheme", re.compile(r"\bSchemes?\s*S?\d+\b", re.I)),
    ("equation", re.compile(r"\bEq(?:uation)?s?\.?\s*\d+\b", re.I)),
    ("supp", re.compile(r"\b(?:SI|Supplementary|Supporting Information)\b", re.I)),
    ("pvalue", re.compile(r"\bp\s*[<=>]\s*0?\.\d+\b", re.I)),
    ("n_count", re.compile(r"\bn\s*=\s*\d+\b", re.I)),
    ("percent", re.compile(r"\b\d+(?:\.\d+)?\s*%")),
    ("mz", re.compile(r"\bm/z\s*=?\s*\d+(?:\.\d+)?\b", re.I)),
]
# Sentence splitter: split on ., !, ? followed by whitespace, but not on a decimal point or a
# lower.Upper run inside a token. Conservative — keeps "Fig. 2" and "0.05" intact.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
# Words that look like a sentence-ending period but are abbreviations (don't split after).
_ABBREV = re.compile(r"\b(?:Fig|Eq|cf|vs|approx|ca|e\.g|i\.e|Dr|Tab)\.\s*$", re.I)


def _split_sentences(text: str) -> list[str]:
    """Conservative sentence split that survives 'Fig. 2', '0.05', 'm/z' and 'e.g.'."""
    raw = [s.strip() for s in _SENT_SPLIT.split((text or "").strip()) if s.strip()]
    # Re-glue a fragment whose predecessor ended in a known abbreviation (over-split guard).
    out: list[str] = []
    for s in raw:
        if out and _ABBREV.search(out[-1]):
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out


def strongest_strength_word(text: str) -> str | None:
    """The single strongest verb-tier word actually present in `text` (reuses induction's ladder).

    Scans STRONG → MODERATE → WEAK and returns the first matching cue, so a sentence is tagged by its
    strongest verb (overclaim is the failure mode we surface). None if no ladder word is present."""
    t = (text or "").lower()
    for tier in (STRONG, MODERATE, WEAK):
        for w in tier:
            if w in t:
                return w.strip()
    return None


def claim_preparse(text: str, *, data_ids: tuple[str, ...] | list[str] = ()) -> list[dict]:
    """PURE pre-parser: split a synthesis/results paragraph into candidate claim records.

    Moves 'structuring claims' off the model: for each sentence it extracts the citation/evidence
    tokens (any of `data_ids` it names verbatim, plus matched patterns — Fig./Table S?/p-values/n=/
    percentages/m/z/SI), the strongest verb-tier word present, and whether any evidence is attached.
    The records feed `audit_claims`, which scores strength and raises the flags. Pure, deterministic,
    stdlib regex only — never invents a citation or a claim.

    Returns a list of {sentence, cites, strength_word, has_evidence}. `cites` is de-duplicated,
    order-preserving (data-ids first, then pattern hits)."""
    records: list[dict] = []
    ids = [str(d) for d in (data_ids or []) if str(d).strip()]
    for sent in _split_sentences(text):
        cites: list[str] = []
        seen: set[str] = set()
        # 1. explicit data-ids the sentence names verbatim (word-boundary, case-insensitive).
        for d in ids:
            if d.lower() in seen:
                continue
            if re.search(r"(?<!\w)" + re.escape(d) + r"(?!\w)", sent, re.I):
                cites.append(d)
                seen.add(d.lower())
        # 2. structured evidence tokens (figures, tables, p-values, n=, %, m/z, SI …).
        for _kind, pat in _CITE_PATTERNS:
            for m in pat.finditer(sent):
                tok = re.sub(r"\s+", " ", m.group(0).strip())
                if tok.lower() not in seen:
                    cites.append(tok)
                    seen.add(tok.lower())
        records.append({
            "sentence": sent,
            "cites": cites,
            "strength_word": strongest_strength_word(sent),
            "has_evidence": bool(cites),
        })
    return records


def format_audit(aud: dict) -> str:
    """Human-readable summary for the CLI."""
    head = (f"induction audit — {aud['n_claims']} claim(s), {aud['n_strong']} strong; "
            f"{len(aud['flags'])} flag(s)")
    if not aud["flags"]:
        return head + "\n  ✓ every claim is evidenced, strength-calibrated, and bounded"
    lines = [head]
    for f in aud["flags"]:
        lines.append(f"  ⚠ [{f['type']}] {f['claim'][:80]}\n      ↳ {f['detail']}")
    return "\n".join(lines)
