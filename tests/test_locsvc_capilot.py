import unittest

from copilot.comparison_engine import (
    PricePlan,
    PriceTier,
    compare_capabilities,
    compare_coverage,
    compare_limits,
    compare_provider_pricing,
    deterministic_cost_estimate,
    normalize_billing_unit,
)
from copilot.conversation_state import ConversationState
from copilot.registered_tools.tool_registry import (
    ComparisonTool,
    DocumentSearchTool,
    SandboxRecordUpdateTool,
    ToolRegistry,
)


class TestComparisonEngine(unittest.TestCase):
    def test_normalize_billing_units(self):
        cases = [
            (100.0, "request", 100.0),
            (250.0, "calls", 250.0),
            (2.0, "1k_requests", 2000.0),
            (1.5, "thousand_calls", 1500.0),
            (3.0, "transactions", 3.0),
        ]
        for value, unit, expected in cases:
            with self.subTest(value=value, unit=unit):
                self.assertAlmostEqual(normalize_billing_unit(value, unit), expected)

        with self.assertRaises(ValueError):
            normalize_billing_unit(10, "not_a_unit")

    def test_deterministic_cost_estimate_paygo(self):
        plan = PricePlan(provider="Alpha", api="directions", currency="USD", unit="request", free_quota=50.0, pay_as_you_go_rate=0.01)
        self.assertAlmostEqual(deterministic_cost_estimate(plan, 100.0, monthly_usage_unit="request"), 0.5)
        self.assertAlmostEqual(deterministic_cost_estimate(plan, 40.0, monthly_usage_unit="request"), 0.0)
        self.assertAlmostEqual(deterministic_cost_estimate(plan, 500.0, monthly_usage_unit="request"), 4.5)

    def test_deterministic_cost_estimate_tiered(self):
        plan = PricePlan(
            provider="Beta",
            api="distance_matrix",
            currency="USD",
            unit="request",
            free_quota=10.0,
            tiers=[
                PriceTier(0.0, 100.0, 0.005),
                PriceTier(100.0, 500.0, 0.003),
            ],
            pay_as_you_go_rate=0.002,
        )
        self.assertAlmostEqual(deterministic_cost_estimate(plan, 350.0, monthly_usage_unit="request"), 1.22)
        self.assertAlmostEqual(deterministic_cost_estimate(plan, 600.0, monthly_usage_unit="request"), 1.88)

    def test_deterministic_cost_estimate_missing_data(self):
        plan = PricePlan(provider="Gamma", api="autocomplete", currency="USD", unit="request")
        self.assertIsNone(deterministic_cost_estimate(plan, 250.0, monthly_usage_unit="request"))

    def test_compare_provider_pricing(self):
        plans = {
            "Google": PricePlan(
                provider="Google",
                api="directions",
                currency="USD",
                unit="request",
                free_quota=100.0,
                pay_as_you_go_rate=0.02,
                source_url="https://example.com/google-pricing",
            ),
            "Mapbox": PricePlan(
                provider="Mapbox",
                api="directions",
                currency="USD",
                unit="request",
                free_quota=50.0,
                pay_as_you_go_rate=0.015,
                source_url="https://example.com/mapbox-pricing",
            ),
        }
        result = compare_provider_pricing("directions", 400.0, plans, region="India")
        self.assertEqual(result["requested_api"], "directions")
        self.assertEqual(result["geographic_region"], "India")
        self.assertEqual(result["providers"], ["Google", "Mapbox"])
        self.assertAlmostEqual(result["calculated_costs"]["Google"], 6.0)
        self.assertAlmostEqual(result["calculated_costs"]["Mapbox"], 5.25)
        self.assertIn("source_references", result)

    def test_compare_capabilities(self):
        matrix = {
            "Google": {
                "directions": {
                    "travel_modes": {"status": "supported", "details": "Driving and walking supported."},
                    "alternatives": {"status": "not_supported", "details": "Alternatives are not available."},
                    "traffic": {"status": "supported", "details": "Traffic-aware results are supported."},
                }
            },
            "Mapbox": {
                "directions": {
                    "travel_modes": {"status": "supported", "details": "Driving supported."},
                    "alternatives": {"status": "not_documented", "details": "Not documented."},
                    "traffic": {"status": "not_verified", "details": "Not verified."},
                }
            },
        }
        result = compare_capabilities("directions", matrix)
        self.assertEqual(result["providers"]["Google"]["travel_modes"]["status"], "supported")
        self.assertEqual(result["providers"]["Mapbox"]["alternatives"]["status"], "not_documented")
        self.assertEqual(result["providers"]["Google"]["traffic"]["status"], "supported")

    def test_compare_coverage(self):
        coverage = {
            "Google": {"India": "supported", "India_notes": "Public coverage in India.", "US": "supported"},
            "Mapbox": {"India": "not_documented", "India_notes": "No approved region statement."},
        }
        result = compare_coverage("directions", coverage, "India")
        self.assertEqual(result["providers"]["Google"]["status"], "supported")
        self.assertEqual(result["providers"]["Mapbox"]["status"], "not_documented")

    def test_compare_limits(self):
        limits = {
            "Google": {"max_batch_size": "50", "rate_limit": "100 RPM"},
            "Mapbox": {"max_batch_size": "25", "rate_limit": "80 RPM"},
        }
        result = compare_limits("distance_matrix", limits)
        self.assertEqual(result["requested_api"], "distance_matrix")
        self.assertEqual(result["providers"]["Google"]["max_batch_size"], "50")
        self.assertEqual(result["providers"]["Mapbox"]["rate_limit"], "80 RPM")


class TestToolRegistry(unittest.TestCase):
    def test_registry_accepts_valid_tool_and_rejects_invalid(self):
        registry = ToolRegistry()
        registry.register(
            DocumentSearchTool(
                documents=[
                    {
                        "document_id": "doc-1",
                        "document_title": "Directions API docs",
                        "source_url": "https://example.com/directions",
                        "relevant_passage": "Directions supports driving and walking modes.",
                        "relevance_score": 0.96,
                        "document_type": "official",
                    }
                ]
            ).tool_definition()
        )
        registry.register(
            ComparisonTool(lambda args: {"requested_api": args["api"], "providers": ["Google"]}).tool_definition()
        )
        registry.register(
            SandboxRecordUpdateTool().tool_definition()
        )

        search_result = registry.execute("document_search", {"query": "walking", "max_results": 2})
        self.assertEqual(search_result["results"][0]["document_id"], "doc-1")

        comparison_result = registry.execute("compare_providers", {"api": "directions", "monthly_usage": 500, "provider_plans": {}})
        self.assertEqual(comparison_result["requested_api"], "directions")

        proposal = registry.execute(
            "sandbox_record_update",
            {
                "record_id": "rec-1",
                "field_name": "monthly_volume",
                "previous_value": 100000,
                "proposed_value": 250000,
                "reason": "Customer confirmed revised monthly volume.",
            },
        )
        self.assertEqual(proposal["status"], "pending_human_approval")
        self.assertEqual(len(registry.execution_log), 3)

        with self.assertRaises(KeyError):
            registry.execute("not_real_tool", {})

        with self.assertRaises(ValueError):
            registry.execute("document_search", {"query": 101})

    def test_tool_registry_exposes_function_specs(self):
        registry = ToolRegistry()
        registry.register(DocumentSearchTool().tool_definition())
        specs = [tool.as_openai_function() for tool in [DocumentSearchTool().tool_definition()]]
        self.assertEqual(specs[0]["function"]["name"], "document_search")


class TestConversationState(unittest.TestCase):
    def test_question_tracking_and_reuse(self):
        state = ConversationState("conv-1")
        self.assertTrue(state.ask_question("What monthly volume do you need?"))
        self.assertFalse(state.ask_question("What monthly volume do you need?"))
        state.answer_question("What monthly volume do you need?")
        self.assertIn("What monthly volume do you need?", state.questions_answered)

    def test_corrections_and_missing_information(self):
        state = ConversationState("conv-2")
        state.add_known_fact("api", "directions")
        state.add_missing_information("region")
        state.apply_correction("api", "distance_matrix", reason="Customer clarified the API.")
        self.assertEqual(state.known_facts["api"], "distance_matrix")
        self.assertIn("region", state.missing_information)
        self.assertEqual(len(state.corrections), 1)

    def test_diagnostic_history_and_summary(self):
        state = ConversationState("conv-3")
        state.add_diagnostic_step("Checked API docs for travel modes.")
        state.add_unresolved_issue("Need confirmation on geographic coverage.")
        state.add_known_fact("region", "India")
        summary = state.build_summary()
        self.assertIn("Conversation conv-3", summary)
        self.assertIn("region=India", summary)
        self.assertIn("Need confirmation on geographic coverage.", state.unresolved_issues)

    def test_isolation_between_conversations(self):
        left = ConversationState("left")
        right = ConversationState("right")
        left.add_known_fact("api", "autocomplete")
        right.add_known_fact("api", "reverse_geocode")
        self.assertEqual(left.known_facts["api"], "autocomplete")
        self.assertEqual(right.known_facts["api"], "reverse_geocode")


if __name__ == "__main__":
    unittest.main()
