#!/usr/bin/env bash
set -euo pipefail

# 24h burn-in monitor for FastAPI + Ollama.
# Usage:
#   bash scripts/soak_24h.sh
#   BASE_URL=http://127.0.0.1:8000 DURATION_HOURS=24 INTERVAL_SEC=60 bash scripts/soak_24h.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
DURATION_HOURS="${DURATION_HOURS:-24}"
INTERVAL_SEC="${INTERVAL_SEC:-60}"
CHAT_EVERY_N="${CHAT_EVERY_N:-5}"  # run /chat smoke every N loops
OUT_DIR="${OUT_DIR:-data}"

mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$OUT_DIR/soak-${TS}.csv"

start_epoch="$(date +%s)"
end_epoch="$((start_epoch + DURATION_HOURS * 3600))"

loops=0
health_ok=0
health_fail=0
chat_ok=0
chat_fail=0

echo "timestamp,health_code,health_ms,chat_code,chat_ms,chat_ok" > "$LOG_FILE"

echo "[soak] start: $(date)"
echo "[soak] base_url=$BASE_URL duration_hours=$DURATION_HOURS interval_sec=$INTERVAL_SEC chat_every_n=$CHAT_EVERY_N"
echo "[soak] log_file=$LOG_FILE"

while [ "$(date +%s)" -lt "$end_epoch" ]; do
  loops=$((loops + 1))
  now="$(date '+%Y-%m-%d %H:%M:%S')"

  health_tmp="$(mktemp)"
  health_meta="$(curl -sS -o "$health_tmp" -w '%{http_code} %{time_total}' "$BASE_URL/health" || echo '000 0')"
  health_code="$(echo "$health_meta" | awk '{print $1}')"
  health_ms="$(echo "$health_meta" | awk '{printf "%.0f", $2*1000}')"

  if [ "$health_code" = "200" ]; then
    health_ok=$((health_ok + 1))
  else
    health_fail=$((health_fail + 1))
  fi
  rm -f "$health_tmp"

  chat_code=""
  chat_ms=""
  chat_pass=""

  if [ $((loops % CHAT_EVERY_N)) -eq 0 ]; then
    chat_tmp="$(mktemp)"
    chat_meta="$(curl -sS -o "$chat_tmp" -w '%{http_code} %{time_total}' \
      -X POST "$BASE_URL/chat" \
      -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"reply with one short word"}]}' || echo '000 0')"

    chat_code="$(echo "$chat_meta" | awk '{print $1}')"
    chat_ms="$(echo "$chat_meta" | awk '{printf "%.0f", $2*1000}')"

    if [ "$chat_code" = "200" ] && grep -q '"content"' "$chat_tmp"; then
      chat_ok=$((chat_ok + 1))
      chat_pass="1"
    else
      chat_fail=$((chat_fail + 1))
      chat_pass="0"
    fi
    rm -f "$chat_tmp"
  fi

  echo "$now,$health_code,$health_ms,$chat_code,$chat_ms,$chat_pass" >> "$LOG_FILE"

  echo "[soak] $now health=$health_code(${health_ms}ms) chat=${chat_code:-skip}(${chat_ms:-}ms)"
  sleep "$INTERVAL_SEC"
done

total_health=$((health_ok + health_fail))
if [ "$total_health" -gt 0 ]; then
  health_rate="$(awk -v ok="$health_ok" -v total="$total_health" 'BEGIN { printf "%.2f", (ok/total)*100 }')"
else
  health_rate="0.00"
fi

total_chat=$((chat_ok + chat_fail))
if [ "$total_chat" -gt 0 ]; then
  chat_rate="$(awk -v ok="$chat_ok" -v total="$total_chat" 'BEGIN { printf "%.2f", (ok/total)*100 }')"
else
  chat_rate="0.00"
fi

echo "[soak] done: $(date)"
echo "[soak] health_ok=$health_ok health_fail=$health_fail availability=${health_rate}%"
echo "[soak] chat_ok=$chat_ok chat_fail=$chat_fail success=${chat_rate}%"
echo "[soak] csv=$LOG_FILE"
