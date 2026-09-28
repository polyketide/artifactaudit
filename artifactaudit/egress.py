"""Egress policy (data-exfiltration boundary) — the in-process half of a two-layer defense.

Layer 1 (authoritative): OS-level — run the agent under `sandbox/agent.sb` (macOS Seatbelt) so
the process *physically* cannot open an outbound socket or write outside its workspace. Prompt
tricks can't bypass the kernel. See sandbox/README.md.

Layer 2 (this file, defense-in-depth): a host **allowlist** the gate consults, so any tool that
would reach a non-allowlisted host (a WebFetch URL, a `curl`/`wget` in Bash) is denied *before* it
runs. This is still in-process and heuristic — it backstops the OS layer and gives a clear reason,
it does not replace it. Pure stdlib; unit-tested offline.
"""
from __future__ import annotations

import re
import urllib.parse

# The hosts a process is allowed to reach. Everything else is treated as potential exfiltration and
# denied before the call runs. Keep this list minimal, and keep the comments to one word: a roster of
# databases is itself informative about what the work is, which is the opposite of the point.
ALLOWED_HOSTS = frozenset({
    "eutils.ncbi.nlm.nih.gov",          # PubMed
    "www.ebi.ac.uk",                    # EBI / Europe PMC
    "ebi.ac.uk",                        # EBI / Europe PMC
    "api.crossref.org",                 # Crossref
    "rest.uniprot.org",                 # UniProt
    "www.rhea-db.org",                  # Rhea
    "rest.kegg.jp",                     # KEGG
    "reactome.org",                     # Reactome
    "string-db.org",                    # STRING
    "mibig.secondarymetabolites.org",   # MIBiG
    "dl.secondarymetabolites.org",      # MIBiG archive
    "www.npatlas.org",                  # NPAtlas
    "coconut.naturalproducts.net",      # COCONUT
    "coconut.s3.uni-jena.de",           # COCONUT dump
    "files.rcsb.org",                   # PDB coordinates
    "www.ncbi.nlm.nih.gov",             # PMC OA service
    "pmc.ncbi.nlm.nih.gov",             # PMC article HTML
    "cdn.ncbi.nlm.nih.gov",             # PMC figure images
    "doi.org",                          # DOI metadata
    "raw.githubusercontent.com",        # CSL styles
})

def assert_airgap() -> None:
    """Empty the allowlist IN-PROCESS so any URL is treated as exfiltration (the soft layer of the
    two-layer air-gap; the kernel sandbox/agent.sb is the hard layer). Idempotent.

    Because is_allowed_host/is_allowed_url/scan_text read the module-global ALLOWED_HOSTS, emptying
    it makes EVERY URL non-allowlisted → scan_text returns (False, [url]) and the registry router +
    gate deny. We rebind the name to a fresh empty frozenset (never mutate in place)."""
    global ALLOWED_HOSTS
    ALLOWED_HOSTS = frozenset()


_URL = re.compile(r"\b(?:https?|ftp)://[^\s'\"|>)]+", re.I)


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url.strip()).hostname or "").lower()
    except Exception:
        return ""


def is_allowed_host(host: str) -> bool:
    """Allow an exact allowlisted host or a subdomain of one (e.g. x.ebi.ac.uk)."""
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def is_allowed_url(url: str) -> bool:
    return is_allowed_host(host_of(url))


def scan_text(text: str) -> tuple[bool, list[str]]:
    """Find URLs in free text (e.g. a shell command); return (all_allowed, offending_urls).

    HONEST LIMIT, and a real one: this finds only http, https and ftp URLs. A command that moves data
    without a URL scheme is invisible to it — `scp file user@host:/path`, `rsync -e ssh`, a git remote
    over SSH, `nc host port`, a DNS channel. For those it returns (True, []), which reads as "nothing
    offending" and is not the same as "nothing leaves". Treat it as a check on the fetch-shaped half of
    the problem; the kernel sandbox is what closes the rest.
    """
    offending = [u for u in _URL.findall(text or "") if not is_allowed_url(u)]
    return (not offending, offending)
