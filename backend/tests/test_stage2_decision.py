"""Stage 2 integration and decision safety tests; no network or credentials required."""
from copy import deepcopy
import unittest
from ai_engine.recommender import recommend
from ai_engine.scoring import latency_score, affordability_score

BASE = {"workload": {"latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                     "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"}}


def request(**overrides):
    payload = deepcopy(BASE)
    payload["workload"].update(overrides)
    return payload


class DecisionEngineStage2(unittest.TestCase):
    def test_backward_compatibility_of_required_response(self):
        r = recommend(BASE)
        keys = ("recommended_tier", "scores", "estimates", "explanation", "tradeoffs", "warnings", "assumptions", "architecture")
        self.assertTrue(all(k in r for k in keys))
        self.assertEqual(r["recommended_tier"], "on_device")
        self.assertEqual(r["details"]["method"], "transparent_weighted_heuristic_v2")
        self.assertEqual(r["details"]["explanation_source"], "deterministic")

    def test_unknown_cost_is_neutral_and_not_presented_as_real_cost(self):
        r = recommend(BASE)
        self.assertIsNone(r["estimates"]["monthly_cost"])
        field = r["details"]["score_breakdown"]["on_device"]["affordability"]
        self.assertEqual(field["origin"], "unknown_neutral_prior")
        self.assertEqual(field["value"], 50)
        self.assertTrue(any("neutral" in s for s in r["warnings"]))

    def test_actual_cost_changes_score_without_faking_other_tiers(self):
        cheap = {"on_device": {"source": "estimated", "monthly_cost_inr": 100}}
        expensive = {"on_device": {"source": "estimated", "monthly_cost_inr": 1800}}
        a = recommend(BASE, metrics_by_tier=cheap)
        b = recommend(BASE, metrics_by_tier=expensive)
        self.assertGreater(a["scores"]["on_device"], b["scores"]["on_device"])
        self.assertEqual(a["details"]["score_breakdown"]["cloud"]["affordability"]["origin"], "unknown_neutral_prior")

    def test_measured_latency_outside_deadline_is_blocked(self):
        m = {"regional_edge": {"source": "measured", "latency_ms": 60}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertEqual(r["scores"]["regional_edge"], 0)
        self.assertFalse(r["details"]["feasibility"]["regional_edge"]["eligible"])

    def test_estimated_latency_outside_deadline_is_soft_penalty(self):
        m = {"regional_edge": {"source": "estimated", "latency_ms": 60}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertTrue(r["details"]["feasibility"]["regional_edge"]["eligible"])
        self.assertEqual(r["details"]["score_breakdown"]["regional_edge"]["latency"]["origin"], "estimated_end_to_end_latency")

    def test_memory_infeasibility(self):
        r = recommend(request(model_ram_required_mb=3072, device_available_ram_mb=2048))
        self.assertFalse(r["details"]["feasibility"]["on_device"]["eligible"])

    def test_offline_and_no_device_ram_yields_no_feasible_tier(self):
        r = recommend(request(require_offline=True, model_ram_required_mb=4096, device_available_ram_mb=1024))
        self.assertIsNone(r["recommended_tier"])

    def test_data_residency_verified_mismatch_blocks(self):
        r = recommend(request(allowed_data_regions=["IN"]), metrics_by_tier={
            "cloud": {"source": "measured", "deployment_region": "EU"}})
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_data_residency_estimate_does_not_claim_verification(self):
        r = recommend(request(allowed_data_regions=["IN"]), metrics_by_tier={
            "cloud": {"source": "estimated", "deployment_region": "EU"}})
        self.assertTrue(r["details"]["feasibility"]["cloud"]["eligible"])
        self.assertTrue(any("region" in g.lower() for g in r["details"]["evidence_gaps"]["cloud"]))

    def test_explicit_verified_residency_failure_blocks(self):
        r = recommend(BASE, metrics_by_tier={"cloud": {"source": "quoted", "data_residency_compliant": False}})
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_unverified_compliance_failure_cannot_block(self):
        r = recommend(BASE, metrics_by_tier={"cloud": {"source": "estimated", "data_residency_compliant": False}})
        self.assertTrue(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_verified_model_incompatibility_blocks(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"source": "measured", "model_compatible": False}})
        self.assertFalse(r["details"]["feasibility"]["on_device"]["eligible"])

    def test_measured_availability_below_declared_minimum_blocks(self):
        r = recommend(request(minimum_availability_percent=99.9), metrics_by_tier={
            "cloud": {"source": "measured", "availability_percent": 99.0}})
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_estimated_availability_below_declared_minimum_does_not_hard_block(self):
        r = recommend(request(minimum_availability_percent=99.9), metrics_by_tier={
            "cloud": {"source": "estimated", "availability_percent": 99.0}})
        self.assertTrue(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_missing_availability_reports_gap(self):
        r = recommend(request(minimum_availability_percent=99.95))
        self.assertTrue(any("availability" in g.lower() for g in r["details"]["evidence_gaps"]["cloud"]))

    def test_benchmark_inference_does_not_become_end_to_end(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"source": "measured", "inference_latency_ms": .45}})
        self.assertIsNone(r["estimates"]["latency_ms"])
        self.assertEqual(r["details"]["score_breakdown"]["on_device"]["latency"]["origin"], "heuristic_profile")

    def test_decision_driver_matches_weighted_difference(self):
        r = recommend(BASE)
        drivers = r["details"]["decision_drivers"]
        self.assertEqual(len(drivers), 6)
        self.assertGreaterEqual(drivers[0]["advantage_points"], drivers[-1]["advantage_points"])
        self.assertEqual(sum(x["advantage_points"] for x in drivers),
                         sum(round(r["details"]["score_breakdown"]["on_device"][f]["weighted_contribution"]
                                   - r["details"]["score_breakdown"]["far_edge"][f]["weighted_contribution"], 2)
                             for f in r["details"]["weights"]))

    def test_valid_scoring_is_finite(self):
        self.assertTrue(0 <= latency_score(50, 50) <= 100)
        self.assertTrue(0 <= affordability_score(1000, 1000) <= 100)
        self.assertEqual(affordability_score(0, 0), 100)
        self.assertEqual(affordability_score(100, 0), 0)

    def test_reject_invalid_optional_fields(self):
        fields = [
            {"concurrent_users": 4.2}, {"minimum_availability_percent": 110},
            {"allowed_data_regions": []}, {"allowed_data_regions": ["IN", "in"]},
            {"target_device": " "}, {"require_offline": "false"},
        ]
        for overrides in fields:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                recommend(request(**overrides))

    def test_llm_source_and_failure_fallback(self):
        class FakeLLM:
            def explain(self, **kwargs):
                return "On device is provisionally recommended."
        class FailingLLM:
            def explain(self, **kwargs):
                raise TimeoutError()
        self.assertEqual(recommend(BASE, llm=FakeLLM())["details"]["explanation_source"], "qualcomm_llm")
        self.assertEqual(recommend(BASE, llm=FailingLLM())["details"]["explanation_source"], "deterministic")


if __name__ == "__main__":
    unittest.main()
