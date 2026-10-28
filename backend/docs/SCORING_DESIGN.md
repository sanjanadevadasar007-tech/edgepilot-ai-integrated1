# Technical design: Person 2's recommendation algorithm

## The decision pipeline

1. Validate the v1 workload JSON, including all required fields.
2. Accept optional per-tier external figures with a provenance flag (`measured`, `quoted`, `estimated`, or `demo`). Synthetic `demo` figures are NEVER used to calculate recommendations or expose estimates.
3. Apply hard feasibility checks (policy, offline/remote restrictions, network outage, declared minimum bandwidth, device RAM, verified model incompatibility, measured missed latency deadline, quoted budget overruns).
4. Compute 0–100 weighted suitability scores using transparent ordinal profiles; replace heuristic latency/cost factors where independently sourced inputs are available.
5. Rank eligible tiers (tie-break follows `on_device`, `far_edge`, `regional_edge`, `cloud` to be deterministic); return the best or `null` if none.
6. Construct an architecture graph with connected device and selected inference tier.
7. Generate a deterministic, grounded explanation, optionally polished by Qualcomm-hosted LLM without changing decisions or estimates.
8. Return the agreed response plus optional `details` with score breakdown and exclusion reasons.

## Formula

`score_tier = sum(factor_score * importance_weight) / sum(importance_weights)`

**Importance weights** depend on workload preferences. Strict latency, high privacy, large data-transfer demand, high criticality, and concurrent users each alter the relative contribution of the corresponding factor. The `affordability` factor defaults to neutral 50/100 if no pricing is known. All profiles are documented demo priors rather than calibrated evidence.

Factor scores and weight details are returned under `details.score_breakdown` so judges and teammates can audit each result. Scores are suitability indices, **not confidence probabilities**.

### Default ordinal profiles (DEMO ASSUMPTIONS; not benchmarks)

| Tier | Relative latency | Privacy | Data locality | Resilience | Scalability |
|---|---:|---:|---:|---:|---:|
| On-device | 96 | 97 | 95 | 80 | 35 |
| Far edge | 86 | 72 | 78 | 75 | 66 |
| Regional edge | 74 | 65 | 62 | 85 | 85 |
| Cloud | 52 | 48 | 35 | 80 | 98 |

These values are NOT physical milliseconds, security guarantees, or provider prices. Use credible environment-specific data to calibrate and validate before making real deployment decisions. Reliability is especially difficult to infer from tier placement alone; the resilience factor is a qualitative proxy, not a reliability SLA.

### Verified vs estimated vs synthetic

- `measured`: latency from a comparable real end-to-end workload; latency greater than deadline is a hard failure. Inference-only measurement belongs in `inference_latency_ms` and does not trigger hard latency checks.
- `quoted`: written infrastructure price quote; `monthly_cost_inr > budget_monthly` is a hard failure. A quoted latency value is a score input but not treated as a measured hard deadline.
- `estimated`: cost and latency estimates adjust the score but are *soft*, not automatic exclusions.
- `demo`: ignored completely. Never surfaced as an operational prediction.

### Mandatory conditions and unverified conditions

The algorithm excludes a tier only for explicit hard policies, confirmed incompatibility or documented hard constraint values. If the caller does not supply device hardware details or per-tier latency, the algorithm labels its decision **provisional**. It does *not* claim technical compatibility merely because a tier has a high score.

## Limitations requiring future real-world verification

- Model architecture/runtime compatibility, storage, peak RAM during loading and postprocessing
- Device thermal/power constraints and model accuracy after quantization
- User-to-edge geographic routing, network jitter, peak-load degradation and failure domains
- Price currency conversion, provider egress and recurring equipment/maintenance costs
- Sovereignty and privacy requirements beyond a generic `high|medium|low` level
- True end-to-end reliability and failover (not guaranteed by placement)

## Project definitions for ambiguous contest wording

For this hackathon codebase only: **far edge** means a nearby access-network compute location; **regional edge** means a regional datacenter somewhat farther away but typically offering more capacity. Different vendors sometimes name these layers differently. Agree on this with Person 1/3 and include a legend in the dashboard.
