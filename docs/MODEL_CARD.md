# Model Card

## Intended use

Demonstrate incident detection, causal-style recovery prioritization and safe financial-agent design on synthetic payment data.

## Models

| Module | MVP implementation |
|---|---|
| Incident detector | Evidence-weighted temporal slice finder |
| Root-cause ranker | Error-distribution shift plus deterministic ontology |
| Action outcome estimator | One logistic model per action (T-learner) |
| Policy evaluation | Inverse propensity scoring on randomized temporal holdout |
| Explanation | Gemini 2.5 Flash if configured; deterministic grounded fallback |

## Training and evaluation data

The demo generates 3,600 randomized historical failed-payment interventions and 1,800 payment events. A known UPI/PSP/bank degradation is injected into the recent window. Synthetic actions have a known 0.25 logging propensity.

Default seed 42 produces:

- 2,700 policy-training records
- 900 temporal holdout records
- mean per-action holdout AUC around 0.70
- correct recovery of the injected three-dimensional incident cohort

Exact numbers may change when the seed or feature engineering changes.

## Limitations

- All current data is synthetic.
- Results are not production recovery claims.
- Outcome probabilities are not calibrated on real merchant traffic.
- The simulator contains simplified treatment effects.
- IPS can have high variance; production evaluation should use randomized guarded exploration or doubly robust estimators.
- No model should initiate live debits without payment-network rules, customer authorization and merchant approval.

## Safety

- Outreach is blocked for opted-out customers.
- Outreach is blocked after two contacts in seven days.
- Retry is blocked for non-transient failures and after the attempt ceiling.
- High-value or uncertain actions require approval.
- LLM output is explanatory only.
- Execution requests are idempotent in the demo store.
