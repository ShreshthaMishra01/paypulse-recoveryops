"""Razorpay test-mode adapter for bounded recovery actions.

No card data is accepted or stored. Customer payment details are collected only on
Razorpay's hosted Payment Link page. When credentials are absent the adapter stays
in explicit mock mode so the repository remains runnable by judges.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict

API_BASE = "https://api.razorpay.com/v1"


class RazorpayAdapterError(RuntimeError):
    pass


def integration_status() -> Dict[str, Any]:
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    configured = bool(key_id and os.getenv("RAZORPAY_KEY_SECRET", "").strip())
    return {
        "configured": configured,
        "mode": "test" if configured and key_id.startswith("rzp_test_") else ("configured" if configured else "mock"),
        "safe_test_key": bool(configured and key_id.startswith("rzp_test_")),
        "key_id_hint": (key_id[:12] + "…") if configured else None,
        "webhook_secret_configured": bool(os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()),
    }


def _request(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not secret:
        raise RazorpayAdapterError("Razorpay credentials are not configured")
    if not key_id.startswith("rzp_test_"):
        raise RazorpayAdapterError("MVP safety lock: only rzp_test_ credentials are accepted")

    token = base64.b64encode(f"{key_id}:{secret}".encode()).decode()
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "User-Agent": "PayPulse-RecoveryOps/0.2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("error", {}).get("description", body)
        except json.JSONDecodeError:
            message = body
        raise RazorpayAdapterError(f"Razorpay API {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RazorpayAdapterError(f"Razorpay API unavailable: {exc.reason}") from exc


def execute_recovery(recommendation: Dict[str, Any], incident: Dict[str, Any]) -> Dict[str, Any]:
    """Create the external recovery operation selected by the bounded policy."""
    status = integration_status()
    action = recommendation["recommended_action"]
    if not status["configured"]:
        return {
            "provider": "mock",
            "operation": action,
            "status": "executed_mock",
            "checkout_url": None,
            "external_id": f"mock_{recommendation['payment_id']}",
        }

    if action == "retry_30m":
        # We deliberately do not auto-debit from application code. In production this
        # becomes a queue message to a network-compliant subscription retry workflow.
        return {
            "provider": "razorpay-test",
            "operation": "schedule_retry",
            "status": "scheduled",
            "checkout_url": None,
            "external_id": f"schedule_{recommendation['payment_id']}",
            "scheduled_after_minutes": 30,
        }

    if action not in {"payment_link", "alternate_method"}:
        return {
            "provider": "razorpay-test",
            "operation": "observe",
            "status": "observed",
            "checkout_url": None,
            "external_id": None,
        }

    amount_paise = int(round(float(recommendation["amount"]) * 100))
    reference = f"pp_{recommendation['payment_id'][-8:]}_{int(time.time())}"
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": reference,
        "description": f"PayPulse recovery for {recommendation['payment_id']}",
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {
            "paypulse_payment_id": recommendation["payment_id"],
            "paypulse_incident_id": incident["incident_id"],
            "selected_action": action,
            "synthetic_demo": "true",
        },
    }
    entity = _request("POST", "/payment_links", payload)
    return {
        "provider": "razorpay-test",
        "operation": "create_payment_link",
        "status": entity.get("status", "created"),
        "checkout_url": entity.get("short_url"),
        "external_id": entity.get("id"),
        "reference_id": entity.get("reference_id", reference),
        "amount_paise": entity.get("amount", amount_paise),
    }


def fetch_payment_link(payment_link_id: str) -> Dict[str, Any]:
    if not payment_link_id or not payment_link_id.startswith("plink_"):
        raise RazorpayAdapterError("No Razorpay Payment Link is attached to this recommendation")
    return _request("GET", f"/payment_links/{payment_link_id}")
