import os
import sys
import time
import requests
from datetime import datetime

AGENT_CONTROL_URL = os.getenv("AGENT_CONTROL_URL", "http://streaming_telemetry_agent:8080")
BURST_INTERVAL_SEC = int(os.getenv("BURST_INTERVAL_SEC", "15"))
BURST_MBPS = float(os.getenv("BURST_MBPS", "18500.0"))
BURST_DURATION_SEC = float(os.getenv("BURST_DURATION_SEC", "1.2"))

def wait_for_agent():
    print(f"[{datetime.utcnow().isoformat()}Z] Waiting for Telemetry Agent on {AGENT_CONTROL_URL}...")
    for _ in range(30):
        try:
            r = requests.get(f"{AGENT_CONTROL_URL}/health", timeout=2)
            if r.status_code == 200:
                print(f"[+] Connected to Telemetry Agent: {r.json()}")
                return True
        except Exception:
            time.sleep(1)
    return False

def run_traffic_injection_loop():
    if not wait_for_agent():
        print("[-] Agent unavailable, exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"[{datetime.utcnow().isoformat()}Z] Starting GPU All-Reduce Traffic Pattern Generator")
    print(f"[*] Burst Configuration: +{BURST_MBPS} Mbps for {BURST_DURATION_SEC}s every {BURST_INTERVAL_SEC}s")

    while True:
        time.sleep(BURST_INTERVAL_SEC)
        print(f"\n[⚡ TRIGGER] Firing Synchronized GPU All-Reduce Incast Microburst...")
        try:
            resp = requests.post(
                f"{AGENT_CONTROL_URL}/burst/inject",
                json={"burst_mbps": BURST_MBPS, "duration_sec": BURST_DURATION_SEC},
                timeout=5
            )
            print(f"[+] Agent response: {resp.json()}")
        except Exception as e:
            print(f"[-] Failed to trigger burst: {e}")

if __name__ == "__main__":
    run_traffic_injection_loop()
