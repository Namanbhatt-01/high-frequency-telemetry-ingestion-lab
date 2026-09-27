import os
import sys
import time
import json
import socket
import random
import threading
import requests
from datetime import datetime

TELEGRAF_UDP_HOST = os.getenv("TELEGRAF_UDP_HOST", "telegraf")
TELEGRAF_UDP_PORT = int(os.getenv("TELEGRAF_UDP_PORT", "8094"))
TELEGRAF_HTTP_URL = os.getenv("TELEGRAF_HTTP_URL", "http://telegraf:8186/telemetry/push")
SWITCH_ID = os.getenv("SWITCH_ID", "leaf-switch-01.ai-fabric.net")
CADENCE_MS = int(os.getenv("STREAMING_CADENCE_MS", "100"))

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Shared state mutated by traffic generator / burst injector
class FabricState:
    def __init__(self):
        self.lock = threading.Lock()
        self.baseline_rate_mbps = 2500.0  # 2.5 Gbps baseline
        self.burst_rate_mbps = 0.0
        self.queue_depth_percent = 12.5
        self.incast_drops = 0
        self.total_packets_sent = 1000000
        self.total_octets_sent = 1500000000

state = FabricState()

def push_udp(payload_dict):
    try:
        data = json.dumps(payload_dict).encode("utf-8")
        sock.sendto(data, (TELEGRAF_UDP_HOST, TELEGRAF_UDP_PORT))
    except Exception as e:
        print(f"UDP Push Error: {e}", file=sys.stderr)

def streaming_telemetry_loop():
    print(f"[{datetime.utcnow().isoformat()}Z] Starting Cisco Nexus OpenConfig Push Telemetry Agent on {SWITCH_ID}")
    print(f"[*] Push Destination: UDP {TELEGRAF_UDP_HOST}:{TELEGRAF_UDP_PORT} | Interval: {CADENCE_MS}ms")

    last_time = time.time()

    while True:
        now = time.time()
        dt = max(0.001, now - last_time)
        last_time = now
        timestamp_ms = int(now * 1000)

        with state.lock:
            current_rate = state.baseline_rate_mbps + state.burst_rate_mbps + random.uniform(-50.0, 50.0)
            current_rate = max(100.0, current_rate)
            
            # Queue depth dynamics
            if state.burst_rate_mbps > 5000.0:
                target_depth = min(99.5, 75.0 + (state.burst_rate_mbps / 400.0))
                if target_depth > 85.0:
                    delta_drops = int((target_depth - 85.0) * random.uniform(2.0, 6.0))
                    state.incast_drops += delta_drops
                else:
                    delta_drops = 0
            else:
                target_depth = random.uniform(8.0, 18.0)
                delta_drops = 0

            # Smooth convergence
            state.queue_depth_percent += (target_depth - state.queue_depth_percent) * 0.4
            
            octets_delta = int((current_rate * 1000000 / 8) * dt)
            packets_delta = int(octets_delta / 1500)
            state.total_octets_sent += octets_delta
            state.total_packets_sent += packets_delta
            
            q_depth = round(state.queue_depth_percent, 2)
            drops_now = delta_drops
            tot_drops = state.incast_drops
            rate_mbps = round(current_rate, 2)

        # 1. OpenConfig Interface State Counters
        if_payload = {
            "sensor_path": "openconfig-interfaces:interfaces/interface/state/counters",
            "switch_id": SWITCH_ID,
            "interface_name": "Ethernet1/1",
            "traffic_class": "RoCEv2-Priority-3",
            "timestamp_ms": timestamp_ms,
            "rate_mbps_streaming_100ms": rate_mbps,
            "in_octets": state.total_octets_sent,
            "in_unicast_pkts": state.total_packets_sent,
            "out_octets": state.total_octets_sent,
            "out_unicast_pkts": state.total_packets_sent,
            "oper_status": "UP"
        }
        push_udp(if_payload)

        # 2. OpenConfig QoS Queue State (Sub-Second Buffer Headroom)
        qos_payload = {
            "sensor_path": "openconfig-qos:qos/queues/queue/state",
            "switch_id": SWITCH_ID,
            "interface_name": "Ethernet1/1",
            "queue_name": "roce-lossless-queue-3",
            "traffic_class": "PFC-Class-3",
            "timestamp_ms": timestamp_ms,
            "queue_depth_percent": q_depth,
            "buffer_occupancy_percent": q_depth,
            "incast_drops_delta": drops_now,
            "queue_drops_count": tot_drops,
            "pfc_pause_rx_count": int(tot_drops * 1.5)
        }
        push_udp(qos_payload)

        # 3. Simulated SNMP 5-Minute Averaged Gauge (Showing Telemetry Blind Spot)
        # SNMP pollers calculate average rate over 300s window, completely masking sub-second bursts
        snmp_payload = {
            "sensor_path": "legacy-snmp:ifTable/ifEntry",
            "switch_id": SWITCH_ID,
            "interface_name": "Ethernet1/1",
            "timestamp_ms": timestamp_ms,
            "rate_mbps_snmp_simulated_300s": 2500.0 + (state.burst_rate_mbps * 0.05),
            "snmp_poll_interval_sec": 300
        }
        push_udp(snmp_payload)

        time.sleep(CADENCE_MS / 1000.0)

# HTTP Endpoint to allow external trigger of bursts
from http.server import HTTPServer, BaseHTTPRequestHandler

class BurstControlHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/burst/inject":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                params = json.loads(body.decode("utf-8"))
            except:
                params = {}
            burst_mbps = float(params.get("burst_mbps", 18000.0)) # 18 Gbps incast microburst
            duration_sec = float(params.get("duration_sec", 1.5))
            
            threading.Thread(target=self._apply_burst, args=(burst_mbps, duration_sec)).start()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "BURST_INJECTED", "burst_mbps": burst_mbps, "duration_sec": duration_sec}).encode("utf-8"))
        
        elif self.path == "/burst/reset":
            with state.lock:
                state.burst_rate_mbps = 0.0
                state.queue_depth_percent = 12.5
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "RESET_CLEAN"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with state.lock:
                info = {
                    "status": "HEALTHY",
                    "switch_id": SWITCH_ID,
                    "cadence_ms": CADENCE_MS,
                    "current_queue_depth": round(state.queue_depth_percent, 2),
                    "total_incast_drops": state.incast_drops
                }
            self.wfile.write(json.dumps(info).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def _apply_burst(self, burst_mbps, duration_sec):
        print(f"[!] INJECTING SYNCHRONIZED GPU ALL-REDUCE INCAST: +{burst_mbps} Mbps for {duration_sec}s")
        with state.lock:
            state.burst_rate_mbps = burst_mbps
        time.sleep(duration_sec)
        with state.lock:
            state.burst_rate_mbps = 0.0
        print(f"[*] INCAST BURST COMPLETED - Returning to baseline")

if __name__ == "__main__":
    t = threading.Thread(target=streaming_telemetry_loop, daemon=True)
    t.start()
    
    server = HTTPServer(("0.0.0.0", 8080), BurstControlHandler)
    print(f"[*] HTTP Burst Control API listening on :8080")
    server.serve_forever()
