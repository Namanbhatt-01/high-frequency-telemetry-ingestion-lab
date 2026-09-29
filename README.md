# LAB 05: High-Frequency Telemetry Ingestion & Microburst Analysis

[![CI/CD Telemetry Pipeline](https://github.com/Namanbhatt-01/high-frequency-telemetry-ingestion-lab/actions/workflows/telemetry_ci.yml/badge.svg)](https://github.com/Namanbhatt-01/high-frequency-telemetry-ingestion-lab/actions/workflows/telemetry_ci.yml)
[![InfluxDB v2](https://img.shields.io/badge/InfluxDB-v2.7-22ADF6?logo=influxdb&logoColor=white)](https://www.influxdata.com/)
[![Telegraf](https://img.shields.io/badge/Telegraf-v1.28-black?logo=influxdb&logoColor=white)](https://github.com/influxdata/telegraf)
[![Grafana](https://img.shields.io/badge/Grafana-v10.2-F46800?logo=grafana&logoColor=white)](https://grafana.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A reproducible laboratory for evaluating high-frequency push streaming telemetry ingestion (100ms cadence) against traditional 30-second SNMP polling during AI workload incast microbursts.

---

## 1. Problem Statement

Distributed AI training workloads (e.g. LLM All-Reduce collective communication) generate synchronized multi-gigabit bursts that can saturate switch egress buffer headroom in **100 microseconds to 50 milliseconds**. 

Standard network management polling (SNMP pull every 30 to 300 seconds) applies time-window averaging over coarse intervals. As a result, short-lived microbursts that cause packet drops and tail latency spikes appear as `<10%` average utilization in SNMP graphs.

This lab evaluates how high-frequency streaming telemetry (100ms push via Telegraf, InfluxDB v2, and Grafana) captures transient buffer occupancy and drops compared to synthetic SNMP polling.

---

## 2. Measurement Science & Metric Provenance

To maintain scientific credibility, every metric emitted by this laboratory is explicitly categorized:

| Metric Name | InfluxDB Field | Measurement Mode | Ingestion Cadence | Description / Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `queue_depth_percent` | `queue_depth_percent` | **Emulated** | 100 ms | Software queue occupancy modeled in Linux kernel container. |
| `incast_drops_delta` | `incast_drops_delta` | **Measured** | 100 ms | Actual dropped packet counts recorded during synthetic burst injection. |
| `rate_mbps_streaming_100ms` | `rate_mbps_streaming_100ms` | **Measured** | 100 ms | Instantaneous throughput calculated per 100ms window. |
| `snmp_rate_mbps_30s_avg` | `snmp_rate_mbps_30s_avg` | **Simulated** | 30,000 ms | 30-second moving average simulating legacy SNMP polling behavior. |
| `burst_headroom_risk_score` | `risk_score` | **Derived** | On-query | Algorithmic ratio of peak queue occupancy to configured ECN threshold. |

---

## 3. Architecture

```
┌───────────────────────────────────┐
│  Traffic Generator / Burst Engine │
└─────────────────┬─────────────────┘
                  │ Injects synchronized 18.5 Gbps microbursts (1.5s)
                  ▼
┌───────────────────────────────────┐
│     Telemetry Agent Container     │
│  - 100ms Push Sensor Engine       │
│  - OpenConfig QoS / Intf model    │
└─────────────────┬─────────────────┘
                  │ UDP Stream (:8094) / Line Protocol
                  ▼
┌───────────────────────────────────┐
│      Telegraf Collector (:8094)   │
└─────────────────┬─────────────────┘
                  │ Batch microsecond writes
                  ▼
┌───────────────────────────────────┐
│      InfluxDB v2 TSDB (:8086)     │
│   Bucket: `network_telemetry`     │
└─────────────────┬─────────────────┘
                  │ Flux queries
                  ▼
┌───────────────────────────────────┐
│        Grafana Dashboard (:3000)  │
└───────────────────────────────────┘
```

---

## 4. Evidence Envelope Output

The verification suite runs the incast experiment and writes a standard machine-readable evidence envelope to `poc/evidence.json`:

```json
{
  "schema_version": "1.0",
  "experiment": {
    "id": "telemetry-microburst-001",
    "name": "High-Frequency Telemetry Ingestion & Microburst Detection"
  },
  "execution": {
    "run_id": "telemetry-20260929-143000",
    "timestamp": "2026-09-29T14:30:00Z",
    "environment": "docker-compose",
    "platform": "darwin-arm64"
  },
  "measurements": [
    { "metric": "telemetry_sampling_cadence_ms", "value": 100.0, "mode": "emulated" },
    { "metric": "peak_buffer_occupancy_percent", "value": 84.5, "mode": "measured" },
    { "metric": "transient_incast_drops_captured", "value": 412, "mode": "measured" }
  ],
  "assertions": [
    { "id": "TEL-ASSERT-001", "name": "Streaming Telemetry Cadence <= 100ms", "passed": true },
    { "id": "TEL-ASSERT-002", "name": "Microburst Peak Occupancy > 70%", "passed": true }
  ],
  "result": "passed"
}
```

---

## 5. Quickstart & Local Reproduction

### Prerequisites
- Docker & Docker Compose (or OrbStack)
- Python 3.11+

### Run Experiment
```bash
# 1. Start Telemetry Stack
make up

# 2. Run automated validation suite
python3 verify_telemetry_pipeline.py

# 3. Teardown
make down
```

---

## 6. Known Limitations

1. **Software Queueing Boundary**: The telemetry agent generates queue occupancy using software timers in Linux containers; it does not read physical switch ASIC registers (e.g., Broadcom Trident/Tomahawk MMU counters or Cisco Cloud Scale ASIC queue registers).
2. **Traffic Generation**: The burst traffic is synthetic UDP load rather than hardware-accelerated RoCEv2 collective traffic generated by physical NVIDIA H100/A100 GPUs.
3. **Transport Protocol**: The reference implementation streams over UDP/HTTP line protocol; production gNMI typically uses gRPC over HTTP/2 with protobuf encoding.

---

## 7. License

Apache 2.0 License. See [LICENSE](LICENSE) for details.
