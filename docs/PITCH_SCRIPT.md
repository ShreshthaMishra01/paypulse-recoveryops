# Five-minute pitch script

## 0:00–0:35 — Problem

A failed payment is not one problem. It may be a bank outage, a bad VPA, insufficient funds or lost purchase intent. Blind retries waste attempts and customer trust. Existing tools often report gross recovery, even when the customer might have paid anyway.

## 0:35–1:00 — Solution

PayPulse RecoveryOps is an India-first causal revenue incident commander. It detects a payment incident, proves the affected cohort and likely cause, chooses the permitted action with the highest incremental value, and records evidence for every rupee it claims.

## 1:00–2:00 — Incident demo

Replay the incident. Show the 1,800-event stream, UPI failure spike, automatically discovered `UPI + PSP_A + Bank_North` cohort, error-distribution shift, confidence and revenue at risk. Open the Gemini evidence briefing and emphasize that the model only summarizes computed facts.

## 2:00–3:05 — Causal policy demo

Show why success probability is not enough. PayPulse estimates each action against no action, subtracts retry/contact friction, and applies consent and attempt ceilings. Execute a payment-link recommendation, open the Razorpay test checkout, complete it with a published test card, verify status, and show the recovered proof-ledger event. Click execution again to demonstrate idempotency.

## 3:05–3:50 — Evaluation

Compare PayPulse with blind retry. Explain the randomized synthetic logging policy, temporal 25% holdout, inverse propensity scoring and bootstrap 95% interval. Explicitly say the values are model estimates on synthetic data—not production claims.

## 3:50–4:30 — Architecture and AI judgment

Statistics detect the incident, logistic action models estimate outcomes, deterministic code handles money and consent, and Gemini explains evidence. The LLM has no permission to execute financial actions. Razorpay remains the payment execution and routing layer.

## 4:30–5:00 — Close

Payment recovery should not maximize attempts. It should maximize incremental recovered rupees under customer and compliance constraints. PayPulse detects the leak, proves the cause, takes the bounded action and leaves an audit trail.
