# OS egress sandbox

A two-layer boundary for a process that reads **unpublished data**. Use both layers: the Python one is
readable and precise, the kernel one is the one that actually holds.

| Layer | Where | Bypassable by prompt tricks? | What it stops |
|---|---|---|---|
| **1. OS sandbox** (authoritative) | `agent.sb` + `run-sandboxed.sh` (macOS Seatbelt) | **No** — kernel-enforced | any outbound socket; writes outside `STATE_DIR`, `OUT_DIR` and the temp directories |
| **2. In-process gate** (defense in depth) | `sciguard/egress.py`, `sciguard/confidential.py` | heuristic | a fetch or a shell command aimed at a non-allowlisted host, and transmission of a registered sequence — refused *before* it runs, with a reason |

## Use

```bash
# smoke-test the profile on your macOS version first — Seatbelt is version-sensitive
sandbox/run-sandboxed.sh /usr/bin/true

# then run your own process under it
STATE_DIR=./state OUT_DIR=./out sandbox/run-sandboxed.sh python -m your_agent --offline
```

The strict profile denies **all** network, so anything that fetches will fail under it. That is the
point, and there are two ways to live with it:

1. **Split-phase.** Do the network phase unsandboxed (or under a network-permitted profile), write what
   you fetched into `STATE_DIR`, then run the analysis phase sandboxed against that cache. The phase that
   touches unpublished data is the phase with no socket.
2. **Relaxed profile.** A variant that permits network and relies on layer 2's allowlist to constrain
   destinations. Strictly weaker than layer 1 — a bug in the allowlist is now a leak.

Calling `sciguard.egress.assert_airgap()` inside a strict run makes layer 2 agree with layer 1: the
allowlist is emptied in-process, so every URL is treated as exfiltration and the refusal is logged with a
reason instead of surfacing as an opaque socket error.

## What this profile does NOT do

Read it before trusting it, because two of its limits are easy to assume away.

**It grants unrestricted read.** The profile says `(allow file-read*)` on purpose: the process is meant
to read a lot, and confidentiality here comes from having no exit rather than from restricting reads. A
sandboxed process can therefore read any file the user can read, including files that have nothing to
do with the task. If that matters for your threat model, narrow the read rules to the paths you
actually need before using it.

**Writes are not confined to `STATE_DIR` and `OUT_DIR` alone.** The profile also allows writes to
`/private/tmp` and `/private/var/folders`, which is what makes Python usable at all. So "it can only
write to its own directories" is not accurate: it can also write to the system temp directories, and
anything with access to those can read what it left there.

**The split-phase pattern has a seam.** The sandboxed phase writes into `STATE_DIR`, and the
network-permitted phase reads it. That shared cache is a channel between a phase that sees unpublished
data and a phase that can reach the network. Keeping the two phases honest is a matter of what you put
in the cache, and the kernel does not enforce it for you.

## Notes

- `sandbox-exec` is macOS-only and version-sensitive. **Test the profile before trusting it:**
  `sandbox-exec -f sandbox/agent.sb -D STATE_DIR=/tmp/s -D OUT_DIR=/tmp/o /usr/bin/true`
- **Linux:** a network namespace with no veth, `firejail --net=none`, or `docker run --network=none` with
  the data mounted `:ro` and only the state and output directories writable.
- The profile grants broad `file-read*` on purpose: the process is meant to read a lot. What it cannot do
  is write outside its own directories or reach the network. Confidentiality here comes from the absence
  of an exit, not from restricting reads.
