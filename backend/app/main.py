from __future__ import annotations

import hashlib
import hmac
import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from .gemini import explain_with_gemini
from .razorpay_adapter import (
    RazorpayAdapterError,
    execute_recovery,
    fetch_payment_link,
    integration_status,
)
from .store import store

app = FastAPI(
    title="PayPulse RecoveryOps API",
    version="0.1.0",
    description="Causal revenue-incident investigation and bounded recovery demo.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResetRequest(BaseModel):
    seed: int = Field(default=42, ge=1, le=1_000_000)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "paypulse-api", "version": "0.1.0"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    result = store.dashboard()
    result["integration"] = integration_status()
    return result


@app.post("/api/demo/reset")
def reset(payload: ResetRequest) -> dict:
    result = store.reset(payload.seed)
    result["integration"] = integration_status()
    return result


@app.get("/api/incidents/{incident_id}/explanation")
def incident_explanation(incident_id: str) -> dict:
    if incident_id != store.incident.get("incident_id"):
        raise HTTPException(status_code=404, detail="Incident not found")
    return explain_with_gemini(store.incident)


@app.post("/api/actions/{payment_id}/execute")
def execute_action(payment_id: str) -> dict:
    try:
        return store.execute(payment_id, execute_recovery)
    except KeyError:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RazorpayAdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/actions/{payment_id}/verify")
def verify_action(payment_id: str) -> dict:
    item = next((r for r in store.recommendations if r["payment_id"] == payment_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    external_id = item.get("execution", {}).get("external_id")
    try:
        entity = fetch_payment_link(external_id)
    except RazorpayAdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if entity.get("status") == "paid" or entity.get("payments"):
        return store.mark_recovered(payment_id, f"verify:{external_id}:paid", external_id)
    return {"ok": True, "paid": False, "status": entity.get("status", "unknown")}


@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request) -> dict:
    """Accept only HMAC-verified Razorpay webhooks and close the proof ledger."""
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret is not configured")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("event", "")
    event_hash = hashlib.sha256(body).hexdigest()
    link_entity = event.get("payload", {}).get("payment_link", {}).get("entity", {})
    payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    notes = link_entity.get("notes") or payment_entity.get("notes") or {}
    payment_id = notes.get("paypulse_payment_id")
    external_id = link_entity.get("id") or payment_entity.get("id")

    if event_type not in {"payment_link.paid", "payment.captured"}:
        return {"ok": True, "ignored": True, "event": event_type}
    if not payment_id:
        return {"ok": True, "ignored": True, "reason": "No PayPulse payment reference"}
    try:
        return store.mark_recovered(payment_id, event_hash, external_id)
    except KeyError:
        return {"ok": True, "ignored": True, "reason": "Unknown PayPulse payment reference"}


@app.get("/api/integration")
def integration() -> dict:
    return integration_status()


@app.get("/api/model-card")
def model_card() -> dict:
    data = store.dashboard()
    return {
        "model_card": data["model_card"],
        "experiment": data["experiment"],
        "safety": {
            "shadow_mode_default": True,
            "contact_budget": "<2 outbound contacts in 7 days",
            "retry_ceiling": "<3 attempts",
            "high_value_approval": "Merchant approval above ₹5,000",
            "idempotent_actions": True,
            "llm_can_execute_money_actions": False,
        },
    }
