"""Deterministic synthetic payment and recovery data for the PayPulse demo.

The generator intentionally injects a known UPI incident, so root-cause accuracy and
policy lift can be evaluated honestly without pretending synthetic outcomes are real
merchant results.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

import numpy as np
import pandas as pd

ACTIONS = ["no_action", "retry_30m", "payment_link", "alternate_method"]
ERRORS = [
    "bank_technical_error",
    "insufficient_funds",
    "invalid_vpa",
    "authentication_failed",
    "customer_cancelled",
    "gateway_timeout",
]


def potential_success(error: str, action: str, hour: int, attempts: int) -> float:
    """Ground-truth response surface used only by the synthetic simulator."""
    table: Dict[str, Dict[str, float]] = {
        "bank_technical_error": {
            "no_action": 0.06,
            "retry_30m": 0.55,
            "payment_link": 0.42,
            "alternate_method": 0.70,
        },
        "gateway_timeout": {
            "no_action": 0.08,
            "retry_30m": 0.66,
            "payment_link": 0.38,
            "alternate_method": 0.62,
        },
        "insufficient_funds": {
            "no_action": 0.16,
            "retry_30m": 0.30,
            "payment_link": 0.24,
            "alternate_method": 0.34,
        },
        "invalid_vpa": {
            "no_action": 0.05,
            "retry_30m": 0.08,
            "payment_link": 0.55,
            "alternate_method": 0.68,
        },
        "authentication_failed": {
            "no_action": 0.09,
            "retry_30m": 0.19,
            "payment_link": 0.43,
            "alternate_method": 0.57,
        },
        "customer_cancelled": {
            "no_action": 0.04,
            "retry_30m": 0.05,
            "payment_link": 0.12,
            "alternate_method": 0.15,
        },
    }
    p = table[error][action]
    if error == "insufficient_funds" and action == "retry_30m" and hour in (8, 9, 10):
        p += 0.16
    if attempts >= 2 and action == "retry_30m":
        p -= 0.13
    return float(np.clip(p, 0.01, 0.94))


def _pick_error(rng: np.random.Generator, incident: bool) -> str:
    if incident:
        return str(
            rng.choice(
                ERRORS,
                p=[0.72, 0.06, 0.04, 0.05, 0.03, 0.10],
            )
        )
    return str(
        rng.choice(
            ERRORS,
            p=[0.14, 0.28, 0.12, 0.19, 0.16, 0.11],
        )
    )


def generate_payment_events(seed: int = 42, n: int = 1800) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime(2026, 9, 2, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    rows = []
    methods = ["UPI", "Card", "Netbanking"]
    psps = ["PSP_A", "PSP_B", "PSP_C"]
    banks = ["Bank_North", "Bank_Central", "Bank_South", "Bank_West"]
    devices = ["Android", "iOS", "Web"]

    for i in range(n):
        minute = int(rng.integers(0, 48 * 60))
        ts = start + timedelta(minutes=minute)
        method = str(rng.choice(methods, p=[0.58, 0.29, 0.13]))
        psp = str(rng.choice(psps, p=[0.45, 0.35, 0.20]))
        bank = str(rng.choice(banks, p=[0.31, 0.27, 0.24, 0.18]))
        device = str(rng.choice(devices, p=[0.62, 0.22, 0.16]))
        amount = int(np.clip(rng.lognormal(mean=6.45, sigma=0.75), 99, 12000))
        is_subscription = bool(rng.random() < 0.34)

        incident_window = ts >= start + timedelta(hours=40)
        incident_cohort = (
            incident_window
            and method == "UPI"
            and psp == "PSP_A"
            and bank == "Bank_North"
        )
        base_fail = {"UPI": 0.055, "Card": 0.072, "Netbanking": 0.082}[method]
        if device == "Web":
            base_fail += 0.012
        fail_prob = 0.47 if incident_cohort else base_fail
        failed = bool(rng.random() < fail_prob)
        error = _pick_error(rng, incident_cohort) if failed else "none"

        rows.append(
            {
                "payment_id": f"pay_demo_{i:05d}",
                "customer_id": f"cust_{int(rng.integers(1, 760)):04d}",
                "timestamp": ts,
                "amount": amount,
                "method": method,
                "psp": psp,
                "bank": bank,
                "device": device,
                "is_subscription": is_subscription,
                "status": "failed" if failed else "captured",
                "error_code": error,
                "consent": bool(rng.random() > 0.09),
                "contact_count_7d": int(rng.choice([0, 1, 2, 3], p=[0.61, 0.26, 0.10, 0.03])),
                "attempt_count": int(rng.choice([1, 2, 3], p=[0.68, 0.25, 0.07])),
                "injected_incident": incident_cohort,
            }
        )
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def generate_recovery_history(seed: int = 73, n: int = 3600) -> pd.DataFrame:
    """Randomized logged interventions for offline policy training/evaluation."""
    rng = np.random.default_rng(seed)
    start = datetime(2026, 7, 1, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    rows = []
    for i in range(n):
        error = str(rng.choice(ERRORS, p=[0.18, 0.27, 0.12, 0.18, 0.13, 0.12]))
        action = str(rng.choice(ACTIONS))  # randomized: propensity = 0.25
        hour = int(rng.integers(0, 24))
        attempts = int(rng.choice([1, 2, 3], p=[0.66, 0.25, 0.09]))
        amount = int(np.clip(rng.lognormal(mean=6.5, sigma=0.78), 99, 15000))
        method = str(rng.choice(["UPI", "Card", "Netbanking"], p=[0.56, 0.31, 0.13]))
        psp = str(rng.choice(["PSP_A", "PSP_B", "PSP_C"]))
        bank = str(rng.choice(["Bank_North", "Bank_Central", "Bank_South", "Bank_West"]))
        device = str(rng.choice(["Android", "iOS", "Web"], p=[0.59, 0.23, 0.18]))
        consent = bool(rng.random() > 0.08)
        contacts = int(rng.choice([0, 1, 2, 3], p=[0.60, 0.27, 0.10, 0.03]))
        p = potential_success(error, action, hour, attempts)
        # Small observable context effects make this a meaningful ML problem.
        if method == "UPI" and action == "alternate_method":
            p += 0.04
        if device == "Web" and action == "payment_link":
            p += 0.03
        p = float(np.clip(p, 0.01, 0.96))
        recovered = bool(rng.random() < p)
        rows.append(
            {
                "event_id": f"hist_{i:05d}",
                "timestamp": start + timedelta(minutes=i * 23),
                "amount": amount,
                "method": method,
                "psp": psp,
                "bank": bank,
                "device": device,
                "error_code": error,
                "hour": hour,
                "attempt_count": attempts,
                "consent": consent,
                "contact_count_7d": contacts,
                "logged_action": action,
                "action_propensity": 0.25,
                "recovered": int(recovered),
                "recovered_amount": amount if recovered else 0,
                "true_success_probability": p,
            }
        )
    return pd.DataFrame(rows)


def generate_demo(seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return generate_payment_events(seed), generate_recovery_history(seed + 31)
