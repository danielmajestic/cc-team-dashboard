#!/usr/bin/env bash
# heartbeat-cron.sh — Register agents and send heartbeats every 60s
# Usage: Run via cron or in background: nohup ./heartbeat-cron.sh &

set -euo pipefail

API_BASE="http://localhost:5000"

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

# Send heartbeat for all agents
send_heartbeats() {
    for name in Mat Kat Sam; do
        local agent_id
        agent_id=$(get_agent_id "$name")
        curl -sf -X POST "$API_BASE/api/agents/${agent_id}/heartbeat" \
            -H "Content-Type: application/json" \
            -d '{"status": "online"}' > /dev/null
    done
}

# Main loop
register_agents

echo "Starting heartbeat loop (every 60s). Press Ctrl+C to stop."
while true; do
    send_heartbeats
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Heartbeats sent."
    sleep 60
done
