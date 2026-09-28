#!/usr/bin/env bash
# Run ANY command under the OS egress sandbox (macOS Seatbelt). The process physically cannot open an
# outbound socket or write outside STATE_DIR / OUT_DIR — enforced by the kernel, not by the model and
# not by the Python allowlist. This is the hard layer; artifactaudit/egress.py is the soft one.
#
#   STATE_DIR=./state OUT_DIR=./out sandbox/run-sandboxed.sh python -m your_agent --offline
#   sandbox/run-sandboxed.sh /usr/bin/true            # smoke-test the profile itself
#
# STRICT: the profile denies ALL network. Anything that fetches will fail under it by design — run
# network phases separately and cache into STATE_DIR. See sandbox/README.md.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${STATE_DIR:-$root/state}"
OUT_DIR="${OUT_DIR:-$root/out}"
mkdir -p "$STATE_DIR" "$OUT_DIR"

if ! command -v sandbox-exec >/dev/null 2>&1; then
  echo "sandbox-exec not found (macOS only). On Linux use a network namespace, firejail --net=none," >&2
  echo "or docker run --network=none with your data mounted read-only." >&2
  exit 2
fi

if [ "$#" -eq 0 ]; then
  echo "usage: [STATE_DIR=… OUT_DIR=…] $0 <command> [args…]" >&2
  exit 2
fi

exec sandbox-exec -f "$root/sandbox/agent.sb" \
  -D STATE_DIR="$STATE_DIR" -D OUT_DIR="$OUT_DIR" \
  "$@"
