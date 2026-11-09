#!/usr/bin/env bash
# stack.sh — bring the app up, prove it answers, take it down. No hand-written docker.
#
#   stack.sh up   [URL]    start it (repo's `up` from detect.py, else docker compose up -d --wait),
#                          then poll URL (or $TMN_FDEKIT_HEALTH_URL) until it answers 2xx/3xx
#   stack.sh check URL     one request: prints status + first lines of the body
#   stack.sh logs  [N]     last N lines (default 60) of the compose logs, for when it won't come up
#   stack.sh down          stop what `up` started (always run this when you are done)
#
# Records what it started in <data>/stacks/<repo>.started so `down` stops exactly that,
# and so a forgotten stack is visible later. Output stays short on purpose.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$root" || exit 2
data="${TMN_FDEKIT_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.tmn-fdekit}}/stacks"; mkdir -p "$data"
marker="$data/$(basename "$root").started"
step() { python3 "$here/detect.py" "$root" | python3 -c "import json,sys; s=json.load(sys.stdin)['steps'].get('$1'); print(s['cmd'] if s else '')"; }

wait_url() {
  local url="$1" tries="${TMN_FDEKIT_HEALTH_TRIES:-60}"
  for ((i = 1; i <= tries; i++)); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" || true)"
    if [[ "$code" =~ ^[23] ]]; then echo "UP     $url answered $code after ${i}s"; return 0; fi
    sleep 1
  done
  echo "DOWN   $url never answered 2xx/3xx in ${tries}s (last: ${code:-none}). Run: stack.sh logs"; return 1
}

case "${1:-}" in
  up)
    cmd="$(step up)"
    [[ -z "$cmd" ]] && { echo "no way to start this repo found (no compose file, Makefile up/dev/run, or package.json dev/start)"; exit 1; }
    echo "start  $cmd"
    if [[ "$cmd" == docker\ compose* || "$cmd" == make\ * ]]; then
      log="$data/$(basename "$root").up.log"
      eval "$cmd" >"$log" 2>&1 || { echo "FAIL   start command failed; last lines:"; tail -n 20 "$log" | sed 's/^/       /'; exit 1; }
    else
      # long-running dev server: background it, keep the pid so `down` can stop the whole tree
      log="$data/$(basename "$root").up.log"
      nohup bash -c "$cmd" >"$log" 2>&1 &
      echo "pid $!" >>"$marker"
    fi
    echo "cmd $cmd" >>"$marker"
    url="${2:-${TMN_FDEKIT_HEALTH_URL:-}}"
    [[ -n "$url" ]] && wait_url "$url" || echo "note   no health URL given; pass one to prove it answers"
    ;;
  check)
    url="${2:?usage: stack.sh check URL}"
    body="$(curl -s -w $'\n__STATUS__%{http_code}' --max-time 10 "$url")"
    echo "status ${body##*__STATUS__}"; printf '%s\n' "${body%__STATUS__*}" | head -n 15
    ;;
  logs)
    if ls compose.y*ml docker-compose.y*ml >/dev/null 2>&1; then docker compose logs --tail "${2:-60}" 2>&1 | tail -n "${2:-60}"
    else tail -n "${2:-60}" "$data/$(basename "$root").up.log" 2>/dev/null; fi
    ;;
  down)
    [[ -f "$marker" ]] || { echo "nothing recorded as started for $(basename "$root")"; exit 0; }
    while read -r kind val; do
      if [[ "$kind" == pid ]]; then
        pkill -TERM -P "$val" 2>/dev/null; kill -TERM "$val" 2>/dev/null && echo "stopped pid $val"
      fi
    done <"$marker"
    dcmd="$(step down)"
    if grep -q '^cmd docker compose\|^cmd make' "$marker" && [[ -n "$dcmd" ]]; then
      eval "$dcmd" >/dev/null 2>&1 && echo "down   $dcmd"
    fi
    rm -f "$marker"
    ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
