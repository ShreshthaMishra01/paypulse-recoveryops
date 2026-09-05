"""In-memory demo state and audit ledger."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List

import numpy as np

from .analytics import affected_failures, detect_incident
from .policy import UpliftPolicy, action_breakdown
from .synthetic import generate_demo


def _native(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_native(v) for v in value]
    if isinstance(value, tuple):
        return [_native(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


class DemoStore:
    def __init__(self) -> None:
        self.lock = Lock()
        self.seed = 42
        self.version = 0
        self.events = None
        self.history = None
        self.incident: Dict[str, Any] = {}
        self.recommendations: List[Dict[str, Any]] = []
        self.experiment: Dict[str, Any] = {}
        self.audit: List[Dict[str, Any]] = []
        self.policy = UpliftPolicy()
        self.reset()

    def reset(self, seed: int | None = None) -> Dict[str, Any]:
        with self.lock:
            if seed is not None:
                self.seed = seed
            self.version += 1
            self.events, self.history = generate_demo(self.seed)
            self.incident = detect_incident(self.events)
            affected = affected_failures(self.events, self.incident)
            _, holdout = self.policy.fit(self.history)
            self.recommendations = self.policy.recommend(affected)
            self.experiment = self.policy.evaluate(holdout, affected)
            self.processed_webhooks: set[str] = set()
            self.audit = [
                {
                    "event_id": "audit_detect_001",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": "incident.detected",
                    "actor": "detector",
                    "message": f"Detected {self.incident['title']} with {self.incident['confidence']}% confidence.",
                    "decision": "investigate",
                    "evidence_ref": self.incident["incident_id"],
                },
                {
                    "event_id": "audit_policy_001",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": "policy.generated",
                    "actor": "causal-policy",
                    "message": f"Generated {len(self.recommendations)} bounded recommendations.",
                    "decision": "shadow_mode",
                    "evidence_ref": "IPS-HOLDOUT-001",
                },
            ]
            return self.dashboard()

    def dashboard(self) -> Dict[str, Any]:
        captured = self.events[self.events["status"] == "captured"]
        failed = self.events[self.events["status"] == "failed"]
        auto_count = sum(r["execution_mode"] == "auto" for r in self.recommendations)
        approval_count = sum(r["execution_mode"] == "approval" for r in self.recommendations)
        result = {
            "meta": {
                "project": "PayPulse RecoveryOps",
                "mode": "shadow",
                "dataset": "synthetic",
                "seed": self.seed,
                "version": self.version,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "summary": {
                "payments_analyzed": int(len(self.events)),
                "captured_revenue": round(float(captured["amount"].sum())),
                "failed_revenue": round(float(failed["amount"].sum())),
                "active_incidents": 1,
                "revenue_at_risk": self.incident["revenue_at_risk"],
                "predicted_incremental_recovery": self.experiment["predicted_incremental_current_batch"],
                "auto_safe_actions": auto_count,
                "approval_actions": approval_count,
            },
            "incident": self.incident,
            "experiment": self.experiment,
            "action_breakdown": action_breakdown(self.recommendations),
            "recommendations": self.recommendations[:30],
            "audit": list(reversed(self.audit[-25:])),
            "model_card": {
                "detector": "Evidence-weighted temporal slice finder",
                "outcome_models": "Per-action logistic T-learner",
                "evaluation": "Temporal 75/25 split + IPS randomized holdout",
                "train_rows": self.policy.metrics.get("train_rows", 0),
                "holdout_rows": self.policy.metrics.get("holdout_rows", 0),
                "mean_action_auc": round(self.policy.metrics.get("mean_action_auc", 0.5), 3),
                "money_action_llm": False,
                "known_limitations": [
                    "Synthetic training and transaction data",
                    "No cross-merchant production history",
                    "Action probabilities require calibration before live use",
                ],
            },
        }
        return _native(result)

    def execute(
        self,
        payment_id: str,
        executor: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute once through an injected adapter and retain the external result."""
        with self.lock:
            item = next((r for r in self.recommendations if r["payment_id"] == payment_id), None)
            if not item:
                raise KeyError(payment_id)
            if item["status"] != "recommended":
                execution = item.get("execution", {})
                return {
                    "ok": True,
                    "idempotent_replay": True,
                    "checkout_url": execution.get("checkout_url"),
                    "recommendation": item,
                }
            if item["recommended_action"] == "no_action":
                raise ValueError("Observe-only recommendations cannot be executed")

            # Keeping the lock across this single external test call prevents a double
            # click from creating two links. Production uses a DB idempotency record.
            execution = executor(item, self.incident)
            item["execution"] = execution
            if execution.get("checkout_url"):
                item["status"] = "awaiting_payment"
                item["execution_mode"] = "razorpay_checkout"
            elif execution.get("status") == "scheduled":
                item["status"] = "scheduled"
                item["execution_mode"] = "scheduled_test"
            else:
                item["status"] = "executed"
                item["execution_mode"] = "executed_mock"

            provider = execution.get("provider", "adapter")
            entry = {
                "event_id": f"audit_execute_{len(self.audit) + 1:03d}",
                "time": datetime.now(timezone.utc).isoformat(),
                "type": f"action.{item['status']}",
                "actor": "merchant-approved-agent",
                "message": f"{item['action_label']} sent to {provider} for {payment_id}; idempotency retained.",
                "decision": item["recommended_action"],
                "evidence_ref": self.incident["incident_id"],
                "external_id": execution.get("external_id"),
            }
            self.audit.append(entry)
            return {
                "ok": True,
                "idempotent_replay": False,
                "checkout_url": execution.get("checkout_url"),
                "recommendation": item,
                "audit": entry,
            }

    def mark_recovered(self, payment_id: str, event_id: str, external_id: str | None = None) -> Dict[str, Any]:
        """Idempotently mark a recovery from a verified webhook or API status check."""
        with self.lock:
            if event_id in self.processed_webhooks:
                return {"ok": True, "idempotent_replay": True}
            item = next((r for r in self.recommendations if r["payment_id"] == payment_id), None)
            if not item:
                raise KeyError(payment_id)
            self.processed_webhooks.add(event_id)
            item["status"] = "recovered"
            item["execution_mode"] = "verified_paid"
            item["recovered_at"] = datetime.now(timezone.utc).isoformat()
            entry = {
                "event_id": f"audit_recovered_{len(self.audit) + 1:03d}",
                "time": item["recovered_at"],
                "type": "payment.recovered",
                "actor": "verified-razorpay-event",
                "message": f"Razorpay test payment verified for {payment_id}; recovery ledger closed.",
                "decision": "mark_recovered",
                "evidence_ref": external_id or self.incident["incident_id"],
            }
            self.audit.append(entry)
            return {"ok": True, "idempotent_replay": False, "recommendation": item, "audit": entry}


store = DemoStore()
