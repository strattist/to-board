#!/usr/bin/env bash
# Verify a running stack end to end: start a Session, hold two Guest SSE streams open
# through the web proxy, end the Session, and check that both Guests are notified.
#
#   scripts/check-room-sse.sh [base-url]        # default http://localhost
#   TOKEN=<bearer> scripts/check-room-sse.sh    # when AUTH_DISABLED=false
#
# Needs a Game with Published Content: set GAME_ID, or the first Game that has it is used.
set -euo pipefail
BASE="${1:-http://localhost}"
AUTH=()
[ -n "${TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $TOKEN")
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"; kill $(jobs -p) 2>/dev/null || true' EXIT

GAME_ID="${GAME_ID:-$(curl -fsS "${AUTH[@]}" "$BASE/api/games" | python3 -c 'import json,sys
g=[x for x in json.load(sys.stdin) if x.get("has_published_content")]
print(g[0]["id"] if g else "")')}"
[ -n "$GAME_ID" ] || { echo "FAIL: no Game with Published Content (set GAME_ID)"; exit 1; }

session="$(curl -fsS "${AUTH[@]}" -X POST "$BASE/api/sessions?game_id=$GAME_ID")"
sid="$(python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])' <<<"$session")"
slug="$(python3 -c 'import json,sys;print(json.load(sys.stdin)["room_slug"])' <<<"$session")"
echo "started session $sid room $slug"

curl -sN -m 20 "$BASE/api/room/$slug/events" >"$tmp/a" & curl -sN -m 20 "$BASE/api/room/$slug/events" >"$tmp/b" &
sleep 2
grep -q "connected" "$tmp/a" || { echo "FAIL: Guest stream gave no immediate data (proxy buffering?)"; curl -sS "${AUTH[@]}" -X POST "$BASE/api/sessions/$sid/end" >/dev/null; exit 1; }
curl -fsS "${AUTH[@]}" -X POST "$BASE/api/sessions/$sid/end" >/dev/null
sleep 2
for f in a b; do grep -q "event: session-ended" "$tmp/$f" || { echo "FAIL: Guest $f not notified"; exit 1; }; done
curl -fsS "$BASE/api/room/$slug" | grep -q '"ended":true' || { echo "FAIL: Room not in ended state"; exit 1; }
echo "OK: 2 Guests notified through $BASE and the Room reports ended"
