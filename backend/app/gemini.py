"""Optional Gemini explanation adapter with a deterministic safe fallback."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict


def fallback_explanation(incident: Dict[str, Any]) -> str:
    cohort = ", ".join(f"{k}={v}" for k, v in incident["affected_filters"].items())
    return (
        f"PayPulse detected a material failure-rate increase in {cohort}. "
        f"The cohort moved from {incident['baseline_failure_rate']}% to "
        f"{incident['current_failure_rate']}%, putting approximately "
        f"₹{incident['revenue_at_risk']:,.0f} at risk. The strongest error shift is "
        f"{incident['likely_error']}, consistent with {incident['root_cause'].lower()}. "
        "Use bounded alternate-method or delayed-retry actions, retain a control group, "
        "and restore normal policy only after the failure rate returns to baseline."
    )


def explain_with_gemini(incident: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"provider": "template-fallback", "text": fallback_explanation(incident)}

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    evidence = {
        key: incident[key]
        for key in [
            "title", "affected_filters", "current_failure_rate", "baseline_failure_rate",
            "revenue_at_risk", "likely_error", "root_cause", "confidence", "evidence",
        ]
    }
    prompt = (
        "You are a cautious payment-operations analyst. Explain this incident in at most "
        "110 words. Use only the JSON evidence. Mention uncertainty, recommend bounded "
        "actions, and never claim synthetic money was actually recovered.\n\n"
        + json.dumps(evidence)
    )
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return {"provider": model, "text": text}
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return {
            "provider": "template-fallback",
            "text": fallback_explanation(incident),
            "warning": f"Gemini unavailable; deterministic fallback used ({type(exc).__name__}).",
        }
