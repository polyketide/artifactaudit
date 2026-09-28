# Provenance

## Where this came from

`sciguard` is a **whitelist extraction** from a larger private research agent. The modules here are the
parts that carry no research content: they check artifacts and confine data. The private repository is
not public and will not be. This package is not a mirror of it and cannot be recombined into it.

## How the extraction works

A build script in the private repository copies **only an explicit list of files** into a staging tree,
then refuses to finish unless every gate passes. A whitelist rather than a blacklist, because for a
public repository one missed exclusion is a permanent leak.

The gates, in order. Each aborts the build.

1. **Whitelist copy.** A named file that is missing aborts.
2. **Truncation.** One module carried an embedded self-test whose fixtures were real identifiers and
   which reached into a module that is not shipped. The build cuts the file at that marker; the suite in
   `tests/` replaces it with synthetic fixtures.
3. **Exact rewrites, asserting exactly one match each.** Short provenance sentences are listed in the
   build script. The multi-line rewrites live in a **gitignored** directory, because the *old* side of a
   rewrite is by definition the sensitive text and so cannot live in committed tooling. A missing
   directory is fatal rather than skipped.
4. **Token scan**, over machine paths and credential prefixes in the script plus a gitignored list of
   embargoed names. The scanner **proves itself first**: it plants a known token and aborts if it fails
   to find it, because a scanner that matches nothing reports "clean".
5. **Shape scan**, added after the audit described below. It matches on *shape* rather than on known
   strings: dates, initials in parentheses, journal names, manuscript-status words, references to private
   work, and command-line flags that do not exist in this package. It has its **own** positive control,
   because the token scanner's control proves only the fixed-string grep and would have passed while this
   sweep was silently broken. Every hit must be fixed or appear in an in-script allowlist with a reason.
6. **Numeric scan.** Every decimal literal appearing in a rewrite's *old* side is forbidden anywhere in
   the staged tree. This closes the precise failure of a number scrubbed from one file and then typed
   back in by hand as a "synthetic" fixture in another, and it maintains itself as the rewrite table
   grows. Word-boundary matched, with its own control.
7. **Placeholder gate.** An unfilled template placeholder anywhere in the tree aborts.
8. **Build checks.** Byte-compile, import standalone, run the test suite.

The copyright-holder token is a name by construction, so it is allowlisted **for `LICENSE` alone** and
stays fatal everywhere else. The token was not removed from the scanner's list to make the build pass.

The script does not push and does not create a repository. Publishing is a separate, human decision.

## The pre-publication audit

Before the first commit existed, the candidate tree was audited by seven independent passes — personal
identity, unpublished-research leakage, code correctness after the extraction, truthfulness of the
documentation, licensing and attribution, security of the advertised mechanisms, and fitness as a public
artifact — with every finding then checked by a separate pass that tried to refute it. Forty findings
survived, and a completeness critic found seventeen more gaps. That is why gates 5, 6 and 7 exist: the
worst leak found belonged to a category **no token list could match**, so hand-fixing the findings
without changing the gate would have let the next build reintroduce them.

What the audit changed, beyond the individual fixes:

- **Two modules were dropped rather than patched.** A figure-inspection module interpolated a
  caller-supplied script into an external command, reported success when its optional dependency was
  absent, had no tests, and narrated private project statistics. A trace module wrote unredacted tool
  input to disk, which would have persisted exactly the sequences the confidentiality guard exists to
  stop. Dropping each removed a class of problem instead of narrowing one.
- **One allowlist host was removed entirely**, not merely stripped of its comment: the host served only
  one kind of record, so naming it disclosed a research direction on its own. The remaining comments were
  reduced to a single word each, and the internal dates, module references and rationale notes were cut.
- **Several checks that could not fail were made able to fail** — an audit function that passed any
  object it did not understand, a confidentiality guard that returned "nothing is confidential" when its
  explicitly configured registry was missing, a cache that returned an empty answer forever once asked
  early, and a test written loosely enough to stay green while the behaviour it covered was wrong.
- **A correctness bug was found in the flagship check.** The reference pattern dropped every citation
  carrying a panel letter, so figures that were discussed were reported as never referenced — and the
  README's own example printed the wrong value as a result. Both are fixed and pinned by tests.

## What was changed relative to the private original

- Module docstrings and comments: provenance narration genericised. Where a comment named a venue, gave
  internal dates, or quoted a title page, only the technical rationale was kept.
- One module's ledger-identifier scheme was replaced with two configurable patterns, so the public
  package does not hardcode a particular group's numbering.
- Two comments used real residue labels as examples; these are now generic labels.
- One module's embedded self-test was removed.
- Package renamed and flattened into a single `sciguard/` package. Internal relative imports still
  resolve.
- New files, written for this package and not extracted: `README.md`, this file, `pyproject.toml`,
  `LICENSE`, `sciguard/__init__.py`, everything under `tests/`, the CI workflow, `sandbox/README.md` and
  `sandbox/run-sandboxed.sh`. The last two were rewritten rather than extracted: the originals hardcoded
  the private entry point, so shipping them would have shipped two broken files.

## What is deliberately absent

The private agent's research layer — literature ingestion, structure and docking runners, molecular
dynamics and quantum-chemistry interfaces, the experiment ledger, the skills, the memory store, every
state file, and the confidential-sequence registry itself — is not here and is not extractable from what
is here.

## Test fixtures

Every fixture in `tests/` is invented for the test: the labels, the sequences, the numbers and the
filenames. The sequences are deliberately not real tags or real vectors, because a published
expression-tag sequence would make this paragraph false. Gate 6 enforces the numeric half of the claim
mechanically rather than asserting it.

## Open questions, recorded rather than answered

- **Institutional intellectual property.** The private source repository carries no licence, and the code
  was written during doctoral work. Whether the author may grant MIT is a question for the institution's
  technology-transfer office and the terms of the fellowship. It is recorded here because it has not been
  answered, and nothing in this file should be read as a claim that it has been.
- **The name.** `sciguard` is free on PyPI. Five repositories on GitHub already use the name, all without
  stars, and one of them does overlapping work. The name was kept deliberately; changing it later does not
  reach existing forks.
