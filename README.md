# PayPulse RecoveryOps

**Detect the leak. Prove the cause. Recover the incremental rupee.**

PayPulse is an India-first, causal revenue incident commander for payment operations. It detects merchant-level payment degradation, finds the affected cohort, ranks permitted recovery actions by incremental value, and records evidence for every decision.

> This repository is a buildathon MVP. Its current dataset and recovery results are synthetic and must not be represented as production outcomes.

## Why this is different

A retry model asks: **“Will this payment succeed if retried?”**

PayPulse asks: **“How much more likely is this payment to recover because of this action compared with doing nothing?”**

```text
Action value = amount × causal uplift − action cost − customer friction
```

It then applies deterministic consent, contact-budget, retry-ceiling and approval gates before an action can execute.

## Working demo

The included scenario analyzes 1,800 payment events and injects a recent UPI authorization incident affecting one PSP and bank. PayPulse:

1. Detects the failure-rate shift.
2. Discovers the affected `UPI + PSP_A + Bank_North` cohort.
3. Ranks root-cause evidence and estimates revenue at risk.
4. Trains per-action outcome models on 3,600 randomized synthetic interventions.
5. Chooses among no action, delayed retry, payment link and alternate method.
6. Evaluates against blind retry using a temporal holdout, inverse propensity scoring and a bootstrap interval.
7. Creates Razorpay test Payment Links, verifies payment status, and closes an idempotent recovery proof ledger.

## Screens

- **Incident Command Center** — failure timeline, blast radius, cohort and evidence
- **Causal Policy Evaluation** — PayPulse versus blind retry with holdout interval
- **Recovery Queue** — transaction-level action, uplift, value, confidence and mode
- **Recovery Proof Ledger** — evidence-linked decision and execution history
- **Model Card** — data, evaluation, limits and integration state

## Architecture

```text
Payment events
     ↓
Temporal anomaly detector
     ↓
Automated cohort discovery
     ↓
Root-cause evidence engine
     ↓
Per-action outcome models
     ↓
Incremental uplift scorer
     ↓
Deterministic safety gate
     ↓
Razorpay/mock action adapter
     ↓
Outcome attribution + proof ledger
```

Read the full [architecture](docs/ARCHITECTURE.md), [model card](docs/MODEL_CARD.md), [failure postmortem](docs/FAILURE_POSTMORTEM.md) and [five-minute pitch](docs/PITCH_SCRIPT.md).

## Stack

- **Backend:** Python, FastAPI, pandas, scikit-learn
- **Frontend:** React, Vite, hand-built SVG visualization
- **Models:** per-action logistic T-learner
- **Evaluation:** temporal split, randomized logging policy, inverse propensity scoring, bootstrap CI
- **LLM:** optional Gemini evidence summary with deterministic fallback
- **Payment integration:** real Razorpay test Payment Links, signed webhook ingestion and status verification; mock mode without credentials

## Quick start

Requirements: Python 3.11+ and Node 20+.

```bash
make setup
```

Run the API:

```bash
make api
```

In a second terminal, run the dashboard:

```bash
make web
```

Open `http://localhost:5173`.

## Tests

```bash
make test
```

The suite checks incident detection, consent enforcement, temporal policy evaluation and the frontend production build.

## Optional Gemini setup

```bash
cp backend/.env.example backend/.env
```

Add your key locally:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Never commit `.env` or API secrets. Without a key, the briefing uses an evidence-grounded deterministic template.

## Razorpay test-mode integration

The current project intentionally defaults to **shadow/mock mode**, because no credentials are stored in the repository. Add test-only values to `backend/.env`:

```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

With test credentials configured, approved `payment_link` and `alternate_method` recommendations create real Razorpay test Payment Links. Delayed retries are scheduled without attempting an unauthorized debit. The dashboard can open checkout and verify link status; `/api/webhooks/razorpay` verifies HMAC signatures before closing the recovery ledger. The ML model never receives secret keys or bypasses the deterministic policy gate. See [Razorpay setup](docs/RAZORPAY_SETUP.md).

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/dashboard` | Complete command-center payload |
| POST | `/api/demo/reset` | Rebuild/replay deterministic synthetic scenario |
| GET | `/api/incidents/{id}/explanation` | Gemini or grounded fallback briefing |
| POST | `/api/actions/{payment_id}/execute` | Idempotent test Payment Link creation or bounded mock action |
| POST | `/api/actions/{payment_id}/verify` | Fetch and verify Razorpay Payment Link status |
| POST | `/api/webhooks/razorpay` | HMAC-verified Razorpay payment webhook |
| GET | `/api/integration` | Safe integration status without exposing secrets |
| GET | `/api/model-card` | Evaluation and safety metadata |

Interactive API docs are available at `http://localhost:8000/docs`.

## Safety principles

- LLMs cannot execute money actions.
- No raw card or bank credentials are stored.
- Customer outreach requires consent and remaining contact budget.
- Non-transient failures cannot be silently retried.
- Retry attempts have a hard ceiling.
- High-value or uncertain decisions require merchant approval.
- Every execution is idempotent and evidence-linked.
- The UI clearly labels synthetic/model-estimated results.

## Production roadmap

1. Persist events and action idempotency in Postgres.
2. Replace synthetic outcomes with merchant-consented historical logs.
3. Calibrate outcomes per payment method and merchant.
4. Add doubly robust off-policy evaluation and guarded randomized exploration.
5. Add drift/OOD detection and automatic abstention.
6. Add India payment ontology for UPI Intent, UPI AutoPay, eMandate and bank-specific windows.

## License

MIT
