#!/usr/bin/env bash
# sdg-watchdog.sh - SDG-LOOM プロセス監視スクリプト (cron 用)
#
# systemd を使えない環境 (共有 VPS, コンテナ内等) 向けの
# 簡易的なプロセス監視 + 自動再起動 + ハートビート監視。
#
# 使い方:
#   1. 下記の変数を実環境に合わせて編集
#   2. chmod +x sdg-watchdog.sh
#   3. crontab -e で登録:
#        */5 * * * * /opt/sdg_loom/deploy/sdg-watchdog.sh >> /var/log/sdg-watchdog.log 2>&1
#
# 機能:
#   - プロセス死活監視: pgrep で sdg run を検出、不在なら再起動
#   - ハートビート監視: heartbeat.json の updated_at が
#     STALE_THRESHOLD_SEC 以上古ければプロセスがハングしていると判断し、
#     kill → 再起動
#   - 再起動回数制限: 短時間内の連続再起動を防止

set -euo pipefail

# --- 設定 (実環境に合わせて編集) ---
SDG_DIR="/opt/sdg_loom"
SDG_CMD="${SDG_DIR}/.venv/bin/sdg"
YAML_PATH="${SDG_DIR}/pipeline.yaml"
INPUT_PATH="${SDG_DIR}/data/input.jsonl"
OUTPUT_PATH="${SDG_DIR}/output/result.jsonl"
HEARTBEAT_PATH="/var/run/sdg-loom/heartbeat.json"
PID_FILE="/var/run/sdg-loom/sdg.pid"
LOG_FILE="${SDG_DIR}/output/sdg-run.log"

# ハートビートが何秒以上更新されなければハングとみなすか
STALE_THRESHOLD_SEC=300

# 短時間再起動防止: この秒数以内に再起動した回数をカウント
RESTART_WINDOW_SEC=600
MAX_RESTARTS=3
RESTART_COUNT_FILE="/var/run/sdg-loom/.restart_count"

# --- 関数 ---

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $*"
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    # PID ファイルがない/不正な場合は pgrep でフォールバック
    pgrep -f "sdg run.*--output ${OUTPUT_PATH}" > /dev/null 2>&1
}

check_heartbeat_stale() {
    [ -f "$HEARTBEAT_PATH" ] || return 1

    local updated_at
    updated_at=$(python3 -c "
import json, sys
from datetime import datetime, timezone
try:
    with open('${HEARTBEAT_PATH}') as f:
        data = json.load(f)
    ts = data.get('updated_at', '')
    dt = datetime.fromisoformat(ts)
    age = (datetime.now(timezone.utc) - dt).total_seconds()
    print(int(age))
except Exception:
    print(-1)
" 2>/dev/null || echo "-1")

    if [ "$updated_at" -ge 0 ] && [ "$updated_at" -gt "$STALE_THRESHOLD_SEC" ]; then
        log "WARNING: heartbeat stale (${updated_at}s old, threshold=${STALE_THRESHOLD_SEC}s)"
        return 0  # stale
    fi
    return 1  # fresh or unknown
}

count_recent_restarts() {
    [ -f "$RESTART_COUNT_FILE" ] || { echo 0; return; }
    local now count ts
    now=$(date +%s)
    ts=$(head -1 "$RESTART_COUNT_FILE" 2>/dev/null || echo 0)
    count=$(tail -1 "$RESTART_COUNT_FILE" 2>/dev/null || echo 0)
    if [ $((now - ts)) -gt "$RESTART_WINDOW_SEC" ]; then
        echo 0
    else
        echo "$count"
    fi
}

record_restart() {
    local now count
    now=$(date +%s)
    count=$(count_recent_restarts)
    count=$((count + 1))
    echo "$now" > "$RESTART_COUNT_FILE"
    echo "$count" >> "$RESTART_COUNT_FILE"
}

start_sdg() {
    log "Starting SDG-LOOM..."
    mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$HEARTBEAT_PATH")" "$(dirname "$LOG_FILE")"

    cd "$SDG_DIR"
    nohup "$SDG_CMD" run \
        --yaml "$YAML_PATH" \
        --input "$INPUT_PATH" \
        --output "$OUTPUT_PATH" \
        --resume \
        --adaptive --max-batch 32 \
        --heartbeat "$HEARTBEAT_PATH" \
        >> "$LOG_FILE" 2>&1 &

    local pid=$!
    echo "$pid" > "$PID_FILE"
    record_restart
    log "Started SDG-LOOM (PID=$pid)"
}

stop_sdg() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "Sending SIGTERM to PID=$pid (graceful shutdown)..."
            kill -TERM "$pid" 2>/dev/null || true
            # 最大 120 秒待機
            local waited=0
            while kill -0 "$pid" 2>/dev/null && [ $waited -lt 120 ]; do
                sleep 2
                waited=$((waited + 2))
            done
            if kill -0 "$pid" 2>/dev/null; then
                log "WARNING: Process did not exit after 120s, sending SIGKILL"
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
}

# --- メイン ---

restarts=$(count_recent_restarts)
if [ "$restarts" -ge "$MAX_RESTARTS" ]; then
    log "ERROR: Too many restarts ($restarts in ${RESTART_WINDOW_SEC}s). Giving up."
    log "Manual intervention required. Check logs: $LOG_FILE"
    exit 1
fi

if is_running; then
    # プロセスは動いている → ハートビートの鮮度を確認
    if check_heartbeat_stale; then
        log "Process appears hung (stale heartbeat). Restarting..."
        stop_sdg
        start_sdg
    fi
    # 正常 → 何もしない
else
    # プロセスがいない → 再起動
    log "SDG-LOOM process not found."

    # heartbeat が "completed" なら正常終了 (全行処理完了) → 再起動しない
    if [ -f "$HEARTBEAT_PATH" ]; then
        status=$(python3 -c "
import json
try:
    with open('${HEARTBEAT_PATH}') as f:
        print(json.load(f).get('status', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")
        if [ "$status" = "completed" ]; then
            log "Heartbeat shows 'completed'. All rows processed. Not restarting."
            exit 0
        fi
    fi

    start_sdg
fi
