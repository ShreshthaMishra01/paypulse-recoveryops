import unittest

from app.analytics import affected_failures, detect_incident
from app.policy import UpliftPolicy
from app.synthetic import generate_demo
from app.store import DemoStore


class PayPulseCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events, cls.history = generate_demo(42)

    def test_incident_detected(self):
        incident = detect_incident(self.events)
        self.assertEqual(incident["status"], "active")
        self.assertGreater(incident["current_failure_rate"], incident["baseline_failure_rate"])
        self.assertIn("method", incident["affected_filters"])
        self.assertEqual(incident["affected_filters"]["method"], "UPI")

    def test_policy_never_contacts_opted_out_customer(self):
        incident = detect_incident(self.events)
        rows = affected_failures(self.events, incident).head(8).copy()
        rows["consent"] = False
        policy = UpliftPolicy()
        policy.fit(self.history)
        recommendations = policy.recommend(rows)
        for rec in recommendations:
            self.assertNotIn(rec["recommended_action"], {"payment_link", "alternate_method"})

    def test_temporal_holdout_and_policy_evaluation(self):
        incident = detect_incident(self.events)
        rows = affected_failures(self.events, incident)
        policy = UpliftPolicy()
        _, holdout = policy.fit(self.history)
        result = policy.evaluate(holdout, rows)
        self.assertEqual(result["evaluation_method"], "IPS on randomized synthetic holdout")
        self.assertEqual(result["holdout_size"], len(holdout))
        self.assertIn("ips_95_ci_per_failure", result)

    def test_execution_and_webhook_are_idempotent(self):
        demo = DemoStore()
        item = next(r for r in demo.recommendations if r["recommended_action"] != "no_action")
        fake = lambda rec, incident: {
            "provider": "test", "status": "created", "checkout_url": "https://example.test/link",
            "external_id": "plink_test_1",
        }
        first = demo.execute(item["payment_id"], fake)
        second = demo.execute(item["payment_id"], fake)
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        paid = demo.mark_recovered(item["payment_id"], "evt_hash_1", "plink_test_1")
        replay = demo.mark_recovered(item["payment_id"], "evt_hash_1", "plink_test_1")
        self.assertFalse(paid["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])


if __name__ == "__main__": 
    unittest.main()
