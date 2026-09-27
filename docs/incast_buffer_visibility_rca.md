# Incident Post-Mortem & RCA: AI GPU Cluster Throughput Collapse during All-Reduce Synchronization

**Incident Reference**: INC-2026-8812  
**Severity**: P1 - Critical Workload Degradation  
**Affected Service**: 512-GPU Distributed Llama-3 70B Training Cluster  
**Duration**: 42 Minutes  
**Impact**: Distributed training iteration step time inflated from 450ms to 4,200ms (9.3x slowdown).  

---

## 1. Executive Summary

During distributed All-Reduce gradient synchronization across 64 compute nodes, the AI training framework experienced severe latency tail inflation. Network Operations Center (NOC) dashboards powered by legacy 5-minute SNMP polling reported link utilizations of **under 8%** with **zero drops recorded**, leading the initial triage team to incorrectly conclude that the network was healthy and suspect application-layer CUDA deadlocks.

Upon enabling **100ms Push Streaming Telemetry (TIG Stack)** on the Leaf switch fabric, telemetry engineers immediately discovered that synchronized 400ms microbursts were driving switch shared buffer occupancy to **99.2%**, resulting in **14,200 silent packet drops per All-Reduce cycle** on RoCEv2 Priority Queue 3.

---

## 2. Root Cause Analysis (RCA)

### Timeline of Events
- **14:00 UTC**: AI cluster begins training run step 1,400.
- **14:04 UTC**: GPU step-time spikes from 450ms $\rightarrow$ 4,200ms.
- **14:08 UTC**: NOC checks legacy SNMP NMS dashboards (`ifInOctets`, `ifInDiscards`). Dashboard shows flat 2.1 Gbps traffic on 100 Gbps interfaces (2.1% utilization) and 0 discards.
- **14:18 UTC**: Streaming Telemetry collector activated on `leaf-switch-01`.
- **14:19 UTC**: 100ms sub-second telemetry exposes 18.5 Gbps transient microbursts coinciding exactly with All-Reduce barrier sync, causing buffer queue exhaustion (98.5% occupancy) and instantaneous drop spikes.
- **14:32 UTC**: Buffer headroom profile and WRED / ECN marking thresholds reconfigured.
- **14:42 UTC**: AI training step time recovers to baseline 450ms.

---

## 3. Telemetry Comparison During Incident

```
+--------------------------------------------------------------------------------------------------+
| TELEMETRY FIDELITY SNAPSHOT DURING 400ms ALL-REDUCE MICROBURST                                    |
+--------------------------------------------------------------------------------------------------+
| Parameter                        Legacy SNMP (300s Polling)    Push Streaming Telemetry (100ms)  |
+--------------------------------------------------------------------------------------------------+
| Max Reported Throughput          2.1 Gbps (Averaged)           18.5 Gbps (True Instantaneous)    |
| Buffer Queue Depth Visibility    12.5% (Nominal)               99.2% (Severe Incast Exhaustion)  |
| Drops Detected                   0 Discards                    14,200 Drops / Incast Event       |
| Mean Time to Identify (MTTI)     > 40 Minutes                  < 10 Seconds                      |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. Remediation & Action Items

1. **Decommission SNMP Polling for Buffer Metrics**: All fabric telemetry migrated to gNMI / Dial-Out streaming at 100ms intervals.
2. **Dynamic Buffer Partitioning**: Allocate larger dedicated shared memory headroom to RoCEv2 lossless queues.
3. **PFC & ECN Tuning**: Lower ECN marking threshold (`Kmin`) to trigger RoCEv2 Congestion Notification Packets (CNPs) before buffer drops occur.
