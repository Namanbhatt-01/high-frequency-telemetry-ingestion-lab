# Technical Architecture Memo: High-Frequency Streaming Telemetry vs. Legacy SNMP Polling in AI Data Center Fabrics

**Author**: Antigravity NetDevOps & Telemetry Engineering Team  
**Target Platform**: Cisco Nexus 9000 (NX-OS), Cisco Silicon One ASICs, Cisco Nexus Dashboard (NDB)  
**Standard Equivalents**: gNMI (gRPC Network Management Interface), OpenConfig YANG, TIG Stack (Telegraf, InfluxDB 2.x, Grafana)  

---

## 1. Executive Summary

Modern AI training clusters running distributed Large Language Model (LLM) workloads (e.g. Megatron-LM, DeepSpeed, PyTorch FSDP) generate synchronized **All-Reduce** communication patterns across tens of thousands of GPUs. In an All-Reduce step, compute nodes simultaneously inject multi-gigabit bursts (incast) into switch egress buffers.

These incast events peak and clear within **100 microseconds to 50 milliseconds**. 

Legacy network monitoring frameworks relying on **Simple Network Management Protocol (SNMP)** poll counters every **3 to 5 minutes (300 seconds)**. Mathematically, 300-second polling averages out high-frequency microbursts, resulting in reported link utilizations of `<10%` while GPU clusters suffer catastrophic step-time latency inflation and throughput collapse due to silent buffer drops.

This document establishes the architectural necessity of **Push-Based Streaming Telemetry (gNMI / Dial-Out)** operating at sub-second cadences (100ms–500ms) with direct hardware ASIC sensor offload.

---

## 2. Telemetry Architectural Comparison

```
+--------------------------------------------------------------------------------------------------------------------+
|                                     TELEMETRY ARCHITECTURE COMPARISON                                              |
+--------------------------------------------------------------------------------------------------------------------+

 1. PULL-BASED SNMP MODEL (Legacy NMS / 300s Polling)
    [ NMS Collector ] === (SNMP GETBULK / OID Request) ===> [ Switch CPU (Control Plane) ]
                                                                       | (Slow Internal IPC)
                                                                       v
                                                           [ ASIC Hardware Registers ]
    * Weaknesses:
      - Heavy switch CPU utilization walking MIB tables.
      - 300s polling window masks microsecond incast events (Nyquist-Shannon violation).
      - Counter wrapping and discontinuous rate calculations.

 2. PUSH-BASED STREAMING MODEL (Cisco Nexus Streaming Telemetry / gNMI Dial-Out)
    [ Switch ASIC Pipeline ] ---> [ Hardware Telemetry Engine ] ---> [ High-Speed UDP / gRPC Push Stream ]
                                                                                   |
                                                                                   v (100ms Push Cadence)
                                                                       [ Telegraf Ingestion Buffer ]
                                                                                   |
                                                                                   v
                                                                       [ InfluxDB v2 TSDB + Grafana ]
    * Strengths:
      - Hardware-assisted streaming directly from ASIC line cards.
      - Zero switch CPU load.
      - True instantaneous visibility into buffer queue depth, ECN marking rates, and PFC pauses.
+--------------------------------------------------------------------------------------------------------------------+
```

---

## 3. YANG Sensor-Path Mapping: Cisco NX-OS & OpenConfig

In Cisco NX-OS and open-source streaming telemetry, metrics are organized hierarchically via YANG data models. The table below illustrates the 1:1 mapping between Cisco NX-OS native sensor paths and the OpenConfig schema implemented in Lab 5:

| Telemetry Domain | Cisco NX-OS Native Sensor Path | OpenConfig Standard Schema (Lab 5) | Telemetry Frequency |
| :--- | :--- | :--- | :--- |
| **Interface Counters** | `sys/intf/phys-[eth1/1]/dbg/stats` | `openconfig-interfaces:interfaces/interface/state/counters` | `100 ms` |
| **QoS Buffer Occupancy**| `sys/pkg/qos/mac/queue-stats` | `openconfig-qos:qos/queues/queue/state/avg-queue-depth` | `100 ms` |
| **PFC Flow Control** | `sys/intf/phys-[eth1/1]/pfc/stats` | `openconfig-qos:qos/interfaces/interface/pfc/state` | `100 ms` |
| **Microburst Drops** | `sys/dme/buffer/microburst-drops` | `openconfig-qos:qos/queues/queue/state/incast_drops_delta` | `Instantaneous Event` |

---

## 4. Cisco Nexus Dashboard (NDB) & Insights Alignment

In enterprise AI data centers, Cisco Nexus Dashboard provides unified visualization, anomaly detection, and capacity planning by ingesting streaming telemetry from Cisco Cloud Scale and Silicon One switches:

1. **Nexus Dashboard Insights (NDI)**: Uses hardware telemetry flow tables (FT) and buffer monitoring to identify transient microburst hotspots before they cause TCP retransmissions or RoCEv2 PFC deadlock.
2. **Open-Source TIG Stack Alignment**:
   - **Telegraf** acts as the high-throughput collector (equivalent to Cisco Nexus Dashboard Collector pods).
   - **InfluxDB v2** serves as the columnar time-series storage engine with Flux querying capabilities.
   - **Grafana** delivers sub-second real-time dashboards with automatic moving-window aggregations.

---

## 5. Conclusion & Recommendations

For all AI/ML GPU fabrics (RoCEv2 / InfiniBand-over-Ethernet):
1. **Decommission SNMP** for operational queue depth and drop visibility.
2. **Deploy gNMI / Dial-Out Push Telemetry** at $\le 500\text{ ms}$ cadence on all spine-leaf interconnects.
3. **Configure Microburst Drop Alerting** with zero threshold tolerance on lossless traffic classes.
