# What broke, and how we recovered

## Failure 1 — A polished model with no credible attribution

### What broke

The first product concept optimized `P(payment succeeds)` and planned to report all later successful payments as recovered revenue. That over-credits the model because some customers would recover without intervention.

### Resolution

We changed the objective to incremental treatment uplift:

`P(success | action) − P(success | no action)`

The synthetic logger randomizes actions, preserves propensities, uses a temporal holdout and evaluates the policy with inverse propensity scoring plus a bootstrap interval. The UI labels all monetary outcomes as estimates.

## Failure 2 — Unsafe retry recommendation

### What broke

A purely statistical model could recommend retries for invalid VPA, authentication failure or customer cancellation, and could contact opted-out customers.

### Resolution

We placed a deterministic policy gate after prediction. It checks decline ontology, retry ceiling, consent and seven-day contact budget. The model can rank only actions that pass these gates.

## Failure 3 — Duplicate action execution

### What broke

Financial webhooks and merchant clicks can be delivered more than once. Re-running the same action could generate duplicate links or retries.

### Resolution

Each payment recommendation maintains execution state. Repeated execution returns `idempotent_replay: true` and does not create another audit event. A production version would persist an idempotency key in a transactional database.

## Failure 4 — Frontend production build failed

### What broke

An empty CSS data-URL import was interpreted by PostCSS as a filesystem import, causing the Vite build to fail.

### Resolution

The unnecessary import was removed. The production build and backend test suite now run under `make test`.

## Remaining failure modes

- Gemini/API unavailable: deterministic evidence template is used.
- Low confidence: action moves to merchant approval or observe mode.
- Razorpay unavailable: action remains queued with its idempotency key.
- Out-of-distribution cohort: production design should abstain and request review.
