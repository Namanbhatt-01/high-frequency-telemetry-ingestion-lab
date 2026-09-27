#!/usr/bin/env bash
# ==============================================================================
# Lab 5: High-Frequency Telemetry Ingestion Experiment Runner
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=============================================================================="
echo "    LAB 5: HIGH-FREQUENCY STREAMING TELEMETRY INGESTION (TIG STACK)           "
echo "=============================================================================="
echo "[+] Starting InfluxDB, Telegraf, Grafana, and Telemetry Agent containers..."

docker compose up -d --build

echo "[+] Waiting for InfluxDB v2 TSDB and Telemetry Agent to initialize..."
for i in {1..30}; do
    if curl -s http://localhost:8086/ping >/dev/null 2>&1 && curl -s http://localhost:8080/health >/dev/null 2>&1; then
        echo "[+] Observability & Telemetry stack is healthy."
        break
    fi
    sleep 1
done

echo ""
echo "[+] Running Automated Streaming Telemetry Pipeline Verification..."
python3 verify_telemetry_pipeline.py

echo ""
echo "[+] Running Telemetry Comparison Analysis (Push Streaming vs. SNMP)..."
python3 snmp_comparison/compare_streaming_vs_snmp.py

echo ""
echo "=============================================================================="
echo "🎉 LAB 5 EXPERIMENT COMPLETE!"
echo "   - Grafana Live Dashboards: http://localhost:3000 (admin / admin)"
echo "   - InfluxDB v2 TSDB:        http://localhost:8086 (org: cisco-ai-fabric)"
echo "   - Telemetry Agent API:     http://localhost:8080/health"
echo "=============================================================================="
