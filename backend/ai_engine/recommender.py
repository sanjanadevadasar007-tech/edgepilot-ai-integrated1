"""Stable Person 2 entrypoint: recommend(payload, *, metrics_by_tier=None, llm=None).

No server or credential dependency. No invented cost or end-to-end latency.
The four deployment choices and original response keys remain unchanged.
"""
from .config import TIERS, LABELS, TRADEOFFS
from .validation import validate
from .metrics import normalize_metrics, field_source
from .feasibility import evaluate, evidence_gaps
from .scoring import calculate, weights, decision_drivers
from .architecture import build
from .explain import default_explanation


def _tier_estimates(workload, metrics):
    """Comparison data for all tiers; unknowns stay null and sources stay per field."""
    out = {}
    for tier in TIERS:
        record = metrics.get(tier, {})
        latency, cost = record.get("latency_ms"), record.get("monthly_cost_inr")
        latency_source = field_source(record, "latency_ms") if latency is not None else None
        cost_source = field_source(record, "monthly_cost_inr") if cost is not None else None
        out[tier] = {
            "latency_ms": round(latency, 2) if latency is not None else None,
            "latency_source": latency_source,
            "latency_target_met": latency <= workload["latency_requirement_ms"] if latency is not None else None,
            "latency_target_verified": latency_source == "measured" if latency is not None else False,
            "latency_headroom_ms": round(workload["latency_requirement_ms"] - latency, 2) if latency is not None else None,
            "monthly_cost_inr": round(cost, 2) if cost is not None else None,
            "cost_source": cost_source,
            "budget_met": cost <= workload["budget_monthly"] if cost is not None else None,
            "budget_verified": cost_source in ("measured", "quoted") if cost is not None else False,
            "budget_headroom_inr": round(workload["budget_monthly"] - cost, 2) if cost is not None else None,
            "cost_to_budget_percent": round(100 * cost / workload["budget_monthly"], 1) if cost is not None and workload["budget_monthly"] > 0 else None,
        }
    return out


def recommend(payload, *, metrics_by_tier=None, llm=None):
    workload = validate(payload)
    metrics = normalize_metrics(metrics_by_tier)
    blocked = evaluate(workload, metrics)
    gaps = evidence_gaps(workload, metrics)
    scores, breakdown, status = calculate(workload, metrics, blocked)
    candidates = [tier for tier in TIERS if status[tier] == "eligible"]
    ranked = sorted(candidates, key=lambda tier: (-scores[tier], TIERS.index(tier)))
    winner = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None
    metric = metrics.get(winner, {}) if winner else {}
    cost = metric.get("monthly_cost_inr")
    latency = metric.get("latency_ms")
    estimates = {"latency_ms": round(latency, 2) if latency is not None else None,
                 "monthly_cost": round(cost, 2) if cost is not None else None,
                 "currency": "INR"}

    warnings = ["DEMO HEURISTICS: scores are uncalibrated suitability indices, not probabilities or measured deployment rankings."]
    if not ranked:
        warnings.append("No feasible placement found under the supplied mandatory constraints.")
    if any(blocked[t] for t in TIERS):
        warnings.append("One or more deployment tiers failed hard feasibility checks; see feasibility details.")
    if winner and latency is None:
        warnings.append("No supported end-to-end latency measurement for the recommended tier; latency shown as null.")
    if winner and cost is None:
        warnings.append("No supported monthly cost estimate for the recommended tier; cost shown as null.")
    if winner and any(field_source(metric, name) == "estimated" for name in ("latency_ms", "monthly_cost_inr") if name in metric):
        warnings.append("Reported metric values for the winner are estimates, not verified measurements or price quotes.")
    if "model_ram_required_mb" not in workload or "device_available_ram_mb" not in workload:
        warnings.append("On-device memory feasibility is unverified: model RAM and device available RAM not both provided.")
    if not metrics:
        warnings.append("Tier-level measurements/quotes not supplied; rankings rely on generic qualitative profiles.")
    if any("affordability" in breakdown[t] and breakdown[t]["affordability"]["origin"] == "unknown_neutral_prior" for t in TIERS):
        warnings.append("Some tier costs are unknown; their affordability uses a neutral scoring placeholder, not a verified cost estimate.")
    if winner and gaps[winner]:
        warnings.append("Recommended tier is not fully verified; see details.evidence_gaps for missing checks.")
    assumptions = [
        "'bandwidth_requirement' means data-transfer demand (low/medium/high), not measured network speed.",
        "Tier profiles are illustrative ordinal assumptions, not Qualcomm hardware benchmark results.",
        "Far edge is modeled as access-network compute; regional edge is a more distant regional data center.",
        "High criticality increases resilience priority but does not guarantee uptime or failover.",
        "Low positive bandwidth by itself does not prove an edge/cloud option infeasible; supply minimum_network_bandwidth_mbps for a hard threshold.",
        "Only confirmed constraints eliminate options; missing hardware/network information remains unknown.",
        "A neutral affordability prior of 50 is used where a tier's cost is unknown; this is not a price observation.",
    ]
    if winner and ("latency_ms" in metric or "monthly_cost_inr" in metric):
        assumptions.append(f"Selected tier metric provenance: latency={field_source(metric, 'latency_ms') or 'unknown'}, "
                           f"cost={field_source(metric, 'monthly_cost_inr') or 'unknown'}.")
    deterministic = default_explanation(winner, scores, blocked, workload)
    explanation = deterministic
    explanation_source = "deterministic"
    if llm is not None:
        try:
            text = llm.explain(workload=workload, tier=winner, scores=scores,
                               blocked=blocked, assumptions=assumptions,
                               default_text=deterministic)
            if isinstance(text, str) and text.strip():
                explanation = text.strip()
                explanation_source = "qualcomm_llm"
        except Exception as exc:
            warnings.append(f"Qualcomm explanation unavailable ({type(exc).__name__}); deterministic explanation used.")
    return {
        "recommended_tier": winner,
        "scores": scores,
        "estimates": estimates,
        "explanation": explanation,
        "tradeoffs": TRADEOFFS[winner] if winner else ["No deployment satisfies all declared hard constraints."],
        "warnings": warnings,
        "assumptions": assumptions,
        "architecture": build(winner),
        "details": {
            "status": "provisional" if winner else "no_feasible_tier",
            "ranking": ranked,
            "feasibility": {tier: {"eligible": not bool(blocked[tier]),
                                   "reasons": blocked[tier],
                                   "verification": "partial" if gaps[tier] else "checked"}
                            for tier in TIERS},
            "evidence_gaps": gaps,
            "score_breakdown": breakdown,
            "weights": weights(workload),
            "decision_drivers": decision_drivers(winner, runner_up, breakdown),
            "metric_sources": {tier: record["source"] for tier, record in metrics.items()},
            "metric_provenance": {tier: record["field_evidence"] for tier, record in metrics.items()},
            "tier_estimates": _tier_estimates(workload, metrics),
            "explanation_source": explanation_source,
            "method": "transparent_weighted_heuristic_v2",
        },
    }
