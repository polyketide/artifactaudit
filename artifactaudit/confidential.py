"""Confidential-sequence guard — the ONE hard no-upload line.

Policy: running locally is chiefly a TOKEN-ECONOMY choice, NOT an airgap. Cloud model skills and
public-database connectors are free to use. **Published sequences are fine to send off-host** — they
are public already. The ONLY thing a tool must never transmit is **your own unpublished or
strictly-confidential sequence data.**

Mechanism: a tool that could send a sequence off-host calls `is_confidential(seq)` and refuses ONLY if
it matches a sequence registered in a LOCAL, gitignored registry. Empty/missing registry → nothing is
confidential → allow (default-open — the common case). This replaces the old "block any long sequence"
tripwire, which was over-strict.

Registry: one protein/nucleotide sequence per entry (plain or FASTA), '#' comments ignored. Path =
env `ARTIFACTAUDIT_CONFIDENTIAL_SEQS` (legacy `ENZYME_CONFIDENTIAL_SEQS` still accepted) else
`state/confidential-seqs.txt`, relative to the working directory (private, never committed). Matching
is substring-either-way on the letters-only normal form, so a full paste OR a fragment is caught —
but only down to 20 letters. A registry entry shorter than that is DISCARDED, and a query shorter
than that is never confidential, because short strings match too much to be useful.
Honest limit: exact/substring only — a point-mutated or reverse-complemented variant won't match; this
guards against accidental paste of the real thing, not a determined adversarial transform."""
from __future__ import annotations

import os
import re

ENV_VAR = "ARTIFACTAUDIT_CONFIDENTIAL_SEQS"
ENV_VAR_LEGACY = "ENZYME_CONFIDENTIAL_SEQS"   # accepted, for trees that already set it
_REL_REGISTRY = os.path.join("state", "confidential-seqs.txt")
_MIN_LEN = 20   # shorter "sequences" are too generic to be meaningfully confidential


def registry_path() -> tuple[str, bool]:
    """(path, explicitly_configured). Resolution order, first hit wins:

    1. `$ARTIFACTAUDIT_CONFIDENTIAL_SEQS` (or the legacy `$ENZYME_CONFIDENTIAL_SEQS`) — explicit, and
       therefore fail-CLOSED if it does not exist.
    2. `./state/confidential-seqs.txt` relative to the CURRENT WORKING DIRECTORY. This is the one a
       reader of the README actually creates. Resolving only against the installed package put the
       expected file outside the search path entirely, so a correctly-followed README produced a
       guard that was silently off.
    3. the same path beside the package, for a source checkout.
    """
    env = os.environ.get(ENV_VAR) or os.environ.get(ENV_VAR_LEGACY)
    if env:
        return (env, True)
    cwd = os.path.join(os.getcwd(), _REL_REGISTRY)
    if os.path.exists(cwd):
        return (cwd, False)
    return (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         _REL_REGISTRY), False)


def _norm(s: str) -> str:
    """Letters-only upper-case normal form (drops FASTA headers, digits, whitespace, gaps)."""
    return re.sub(r"[^A-Z]", "", (s or "").upper())


_CACHE: dict[tuple[str, float], frozenset[str]] = {}


def _protected() -> frozenset[str]:
    """The registered sequences. Cached on (path, mtime) rather than on nothing.

    A one-slot cache keyed on no input meant that pointing the guard at a registry AFTER anything had
    already asked a question returned the earlier, empty answer — the guard was off and said nothing.
    """
    path, explicit = registry_path()
    if not os.path.exists(path):
        if explicit:
            # An explicitly configured guard whose registry is missing is a broken guard, not an
            # absent one. Failing closed here is the whole point: a mistyped path must not read as
            # "nothing is confidential".
            raise FileNotFoundError(
                f"ENZYME_CONFIDENTIAL_SEQS points at {path!r}, which does not exist. "
                f"Refusing to report that nothing is confidential. Unset it to disable the guard.")
        return frozenset()
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key in _CACHE:
        return _CACHE[key]
    seqs, cur = set(), []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                t = ln.strip()
                if not t or t.startswith("#"):
                    continue
                if t.startswith(">"):
                    if cur:
                        seqs.add(_norm("".join(cur))); cur = []
                    continue
                cur.append(t)
        if cur:
            seqs.add(_norm("".join(cur)))
    except OSError:
        return frozenset()
    out = frozenset(x for x in seqs if len(x) >= _MIN_LEN)
    _CACHE[key] = out
    return out


def is_confidential(value: str) -> bool:
    """True iff `value` contains (or is contained by) a registered confidential sequence. Default-open:
    with no registry, always False. Cheap letters-only substring check."""
    n = _norm(value)
    if len(n) < _MIN_LEN:
        return False
    return any(n == p or n in p or p in n for p in _protected())


def reload_registry() -> None:
    """Drop the cached registry. Rarely needed now that the cache is keyed on the file's mtime, but
    kept for a same-second edit, which an mtime cannot distinguish."""
    _CACHE.clear()
