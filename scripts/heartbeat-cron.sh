#!/usr/bin/env bash
# heartbeat-cron.sh — Register agents and send heartbeats every 60s
# Detects real tmux state per agent:
#   no session   → offline
#   active output → busy
#   idle prompt   → available
#   WORKING.md says done/complete → complete
# Usage: Run via cron or in background: nohup ./heartbeat-cron.sh &

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:5000}"
AGENTS_DIR="${AGENTS_DIR:-$HOME/agents}"

# Register agents (idempotent — creates if missing, updates if exists)
register_agents() {
    curl -sf -X POST "$API_BASE/api/agents/register" \
        -H "Content-Type: application/json" \
        -d '{"name": "Mat", "role": "pm"}' > /dev/null

    curl -sf -X POST "$API_BASE/api/agents/register" \
        -H "Content-Type: application/json" \
        -d '{"name": "Kat", "role": "backend"}' > /dev/null

    curl -sf -X POST "$API_BASE/api/agents/register" \
        -H "Content-Type: application/json" \
        -d '{"name": "Sam", "role": "frontend"}' > /dev/null

    echo "Agents registered."
}

# Get agent ID by name
get_agent_id() {
    local name="$1"
    curl -sf "$API_BASE/api/agents" | \
        python3 -c "import sys,json; agents=json.load(sys.stdin); print(next(a['id'] for a in agents if a['name']=='$name'))"
}

# Detect real agent status from tmux + WORKING.md
detect_status() {
    local name="$1"
    local session="${name,,}"  # lowercase for tmux session name

    # 1. No tmux session → offline
    if ! tmux has-session -t "$session" 2>/dev/null; then
        echo "offline"
        return
    fi

    # 2. Check WORKING.md for "complete" or "done" status
    local working_file="$AGENTS_DIR/$session/WORKING.md"
    if [[ -f "$working_file" ]]; then
        local status_line
        status_line=$(grep -i '## Current Status:' "$working_file" 2>/dev/null || true)
        if [[ -n "$status_line" ]]; then
            local status_value="${status_line##*:}"
            status_value=$(echo "$status_value" | tr '[:upper:]' '[:lower:]' | xargs)
            if [[ "$status_value" == "complete" || "$status_value" == "done" || "$status_value" == "completed" ]]; then
                echo "complete"
                return
            fi
        fi
    fi

    # 3. Check tmux pane for activity vs idle prompt
    local pane_output
    pane_output=$(tmux capture-pane -p -t "$session" -S -5 2>/dev/null || true)

    # Get last non-empty line
    local last_line
    last_line=$(echo "$pane_output" | grep -v '^[[:space:]]*$' | tail -1)

    # Idle indicators: shell prompt chars or Claude Code prompt
    if echo "$last_line" | grep -qE '(❯|⏵|\$\s*$|>\s*$)'; then
        echo "available"
    else
        echo "busy"
    fi
}

# Send heartbeat for a single agent with detected status
send_heartbeat() {
    local name="$1"
    local agent_id
    agent_id=$(get_agent_id "$name")

    local status
    status=$(detect_status "$name")

    local task=""
    local working_file="$AGENTS_DIR/${name,,}/WORKING.md"
    if [[ -f "$working_file" ]]; then
        task=$(grep -i '^\*\*Last task:\*\*' "$working_file" 2>/dev/null | head -1 | sed 's/\*\*Last task:\*\*\s*//' || true)
    fi

    local payload
    payload=$(python3 -c "import json; print(json.dumps({'status': '$status', 'current_task': '''$task'''}))")

    curl -sf -X POST "$API_BASE/api/agents/${agent_id}/heartbeat" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null

    echo "  $name: $status"
}

# Main loop
register_agents

echo "Starting heartbeat loop (every 60s). Press Ctrl+C to stop."
while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Detecting agent states..."
    for name in Mat Kat Sam; do
        send_heartbeat "$name" || echo "  $name: heartbeat failed"
    done
    sleep 60
done
