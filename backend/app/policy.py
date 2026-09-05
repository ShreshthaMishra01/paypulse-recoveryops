"""Causal-style action uplift estimation and constrained recovery policy.

This is an educational MVP. The logged synthetic interventions are randomized, which
lets us evaluate policies without making claims about production merchant outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .synthetic import ACTIONS

CATEGORICAL = ["method", "psp", "bank", "device", "error_code"]
NUMERIC = ["amount", "hour", "attempt_count", "contact_count_7d"]
ACTION_COST = {"no_action": 0.0, "retry_30m": 1.0, "payment_link": 3.0, "alternate_method": 4.0}
FRICTION_POINTS = {"no_action": 0, "retry_30m": 2, "payment_link": 1, "alternate_method": 2}
FRICTION_RUPEES = 8.0
ACTION_LABELS = {
    "no_action": "Observe — no action",
    "retry_30m": "Retry after 30 minutes",
    "payment_link": "Send secure payment link",
    "alternate_method": "Recommend alternate method",
}


@dataclass
class ConstantModel:
    probability: float

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        p = np.full(len(x), self.probability)
        return np.c_[1 - p, p]


class UpliftPolicy:
    def __init__(self) -> None:
        self.models: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}

    @staticmethod
    def _features(df: pd.DataFrame) -> pd.DataFrame:
        x = df.copy()
        if "hour" not in x.columns:
            x["hour"] = pd.to_datetime(x["timestamp"]).dt.hour
        for col in CATEGORICAL:
            if col not in x.columns:
                x[col] = "unknown"
        for col in NUMERIC:
            if col not in x.columns:
                x[col] = 0
        return x[CATEGORICAL + NUMERIC]

    @staticmethod
    def _pipeline() -> Pipeline:
        prep = ColumnTransformer(
            transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
                ("num", StandardScaler(), NUMERIC),
            ]
        )
        return Pipeline([
            ("prep", prep),
            ("model", LogisticRegression(max_iter=700, C=0.8, class_weight="balanced")),
        ])

    def fit(self, history: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        ordered = history.sort_values("timestamp").reset_index(drop=True)
        split = int(len(ordered) * 0.75)
        train, holdout = ordered.iloc[:split].copy(), ordered.iloc[split:].copy()
        aucs = []
        for action in ACTIONS:
            subset = train[train["logged_action"] == action]
            if subset["recovered"].nunique() < 2:
                model: Any = ConstantModel(float(subset["recovered"].mean()))
            else:
                model = self._pipeline()
                model.fit(self._features(subset), subset["recovered"])
            self.models[action] = model
            test_action = holdout[holdout["logged_action"] == action]
            if len(test_action) and test_action["recovered"].nunique() == 2:
                pred = model.predict_proba(self._features(test_action))[:, 1]
                aucs.append(roc_auc_score(test_action["recovered"], pred))
        self.metrics["mean_action_auc"] = float(np.mean(aucs)) if aucs else 0.5
        self.metrics["train_rows"] = int(len(train))
        self.metrics["holdout_rows"] = int(len(holdout))
        return train, holdout

    def probabilities(self, rows: pd.DataFrame) -> Dict[str, np.ndarray]:
        x = self._features(rows)
        return {action: self.models[action].predict_proba(x)[:, 1] for action in ACTIONS}

    @staticmethod
    def allowed_actions(row: pd.Series) -> Tuple[List[str], List[str]]:
        allowed = ["no_action"]
        blocked_reasons: List[str] = []
        error = str(row.get("error_code", ""))
        attempts = int(row.get("attempt_count", 1))
        consent = bool(row.get("consent", True))
        contacts = int(row.get("contact_count_7d", 0))

        retriable = error in {"bank_technical_error", "gateway_timeout", "insufficient_funds"}
        if retriable and attempts < 3:
            allowed.append("retry_30m")
        elif not retriable:
            blocked_reasons.append("retry blocked: non-transient failure")
        else:
            blocked_reasons.append("retry blocked: attempt ceiling reached")

        if consent and contacts < 2:
            allowed.extend(["payment_link", "alternate_method"])
        elif not consent:
            blocked_reasons.append("outreach blocked: customer opted out")
        else:
            blocked_reasons.append("outreach blocked: 7-day contact budget exhausted")
        return allowed, blocked_reasons

    def recommend(self, rows: pd.DataFrame) -> List[Dict[str, Any]]:
        if rows.empty:
            return []
        probs = self.probabilities(rows)
        outputs: List[Dict[str, Any]] = []
        for pos, (_, row) in enumerate(rows.iterrows()):
            p0 = float(probs["no_action"][pos])
            allowed, blocked = self.allowed_actions(row)
            candidates = []
            for action in allowed:
                p = float(probs[action][pos])
                uplift = p - p0
                value = float(row["amount"]) * uplift - ACTION_COST[action] - FRICTION_RUPEES * FRICTION_POINTS[action]
                candidates.append((value, action, p, uplift))
            value, action, probability, uplift = max(candidates, key=lambda item: item[0])
            # Negative incremental utility means restraint is the correct action.
            if value < 0:
                action = "no_action"
                probability = p0
                uplift = 0.0
                value = 0.0
            confidence = float(np.clip(0.62 + abs(uplift) * 0.45, 0.62, 0.96))
            execution_mode = "auto" if confidence >= 0.82 and float(row["amount"]) <= 5000 else "approval"
            if action == "no_action":
                execution_mode = "observe"
            reason = self._reason(str(row["error_code"]), action)
            outputs.append({
                "payment_id": str(row["payment_id"]),
                "customer_id": str(row["customer_id"]),
                "amount": round(float(row["amount"]), 2),
                "method": str(row["method"]),
                "error_code": str(row["error_code"]),
                "recommended_action": action,
                "action_label": ACTION_LABELS[action],
                "success_probability": round(probability * 100, 1),
                "no_action_probability": round(p0 * 100, 1),
                "incremental_uplift_pp": round(uplift * 100, 1),
                "expected_incremental_value": round(value, 2),
                "confidence": round(confidence * 100, 1),
                "execution_mode": execution_mode,
                "reason": reason,
                "blocked_reasons": blocked,
                "status": "recommended",
            })
        return sorted(outputs, key=lambda item: item["expected_incremental_value"], reverse=True)

    @staticmethod
    def _reason(error: str, action: str) -> str:
        reasons = {
            ("bank_technical_error", "alternate_method"): "Transient bank degradation; alternate rail has the highest incremental lift.",
            ("bank_technical_error", "retry_30m"): "Transient bank degradation; wait for the authorization window to recover.",
            ("gateway_timeout", "retry_30m"): "Likely short-lived timeout; a delayed retry avoids immediate repeat failure.",
            ("invalid_vpa", "payment_link"): "Customer input is required; a fresh link reduces VPA-entry friction.",
            ("invalid_vpa", "alternate_method"): "The current VPA path is unlikely to recover without a method change.",
            ("authentication_failed", "payment_link"): "A fresh authenticated session is more useful than a silent retry.",
            ("authentication_failed", "alternate_method"): "Repeated authentication is unlikely to help; offer a lower-friction method.",
            ("insufficient_funds", "retry_30m"): "Temporary funding issue; retry is permitted within the attempt ceiling.",
            ("customer_cancelled", "no_action"): "Respect possible loss of purchase intent and avoid unnecessary contact.",
        }
        return reasons.get((error, action), "Selected for the highest expected incremental value within policy constraints.")

    def evaluate(self, holdout: pd.DataFrame, current_rows: pd.DataFrame) -> Dict[str, Any]:
        """Offline randomized-policy evaluation plus model-based current batch estimate."""
        holdout = holdout.copy().reset_index(drop=True)
        recs = self.recommend(holdout.assign(
            payment_id=holdout["event_id"],
            customer_id="historical",
        ))
        chosen = np.array([r["recommended_action"] for r in recs])
        # recommend() sorts by value, so map choices back by id.
        chosen_by_id = {r["payment_id"]: r["recommended_action"] for r in recs}
        chosen = holdout["event_id"].map(chosen_by_id).to_numpy()
        match_policy = holdout["logged_action"].to_numpy() == chosen
        propensity = holdout["action_propensity"].to_numpy()
        rewards = holdout["recovered_amount"].to_numpy(dtype=float)
        policy_contribution = np.where(match_policy, rewards / propensity, 0.0)
        baseline_match = holdout["logged_action"].to_numpy() == "retry_30m"
        baseline_contribution = np.where(baseline_match, rewards / propensity, 0.0)
        delta = policy_contribution - baseline_contribution

        rng = np.random.default_rng(2026)
        means = []
        for _ in range(500):
            sample = rng.choice(delta, size=len(delta), replace=True)
            means.append(float(sample.mean()))
        low, high = np.percentile(means, [2.5, 97.5])
        ips_policy = float(policy_contribution.mean())
        ips_baseline = float(baseline_contribution.mean())

        current_recs = self.recommend(current_rows)
        probs = self.probabilities(current_rows) if len(current_rows) else {a: np.array([]) for a in ACTIONS}
        predicted_policy = sum(r["amount"] * r["success_probability"] / 100 for r in current_recs)
        predicted_baseline = float(np.sum(current_rows["amount"].to_numpy() * probs["retry_30m"])) if len(current_rows) else 0.0
        predicted_incremental = predicted_policy - predicted_baseline

        return {
            "evaluation_method": "IPS on randomized synthetic holdout",
            "holdout_size": int(len(holdout)),
            "mean_action_auc": round(self.metrics["mean_action_auc"], 3),
            "ips_policy_value_per_failure": round(ips_policy, 2),
            "ips_blind_retry_value_per_failure": round(ips_baseline, 2),
            "ips_incremental_per_failure": round(ips_policy - ips_baseline, 2),
            "ips_95_ci_per_failure": [round(float(low), 2), round(float(high), 2)],
            "predicted_recovered_current_batch": round(predicted_policy),
            "predicted_blind_retry_current_batch": round(predicted_baseline),
            "predicted_incremental_current_batch": round(predicted_incremental),
            "current_batch_size": int(len(current_rows)),
            "disclaimer": "Model-estimated results on synthetic data; not production recovery claims.",
        }


def action_breakdown(recommendations: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recs = list(recommendations)
    output = []
    for action in ACTIONS:
        selected = [r for r in recs if r["recommended_action"] == action]
        output.append({
            "action": action,
            "label": ACTION_LABELS[action],
            "count": len(selected),
            "expected_incremental_value": round(sum(r["expected_incremental_value"] for r in selected)),
        })
    return output
