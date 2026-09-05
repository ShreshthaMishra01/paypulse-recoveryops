# Razorpay Test-Mode Setup

PayPulse accepts **test keys only**. A non-`rzp_test_` key is rejected by the backend safety lock.

## 1. Configure credentials

In Razorpay Dashboard, switch to Test Mode and generate an API key. Copy the example file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Add values locally:

```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=choose_a_long_random_test_secret
```

Never commit `backend/.env`. Restart the backend after changing it.

Verify safe status:

```text
http://localhost:8000/api/integration
```

Expected fields include `configured: true`, `mode: test`, and `safe_test_key: true`. Secrets are never returned.

## 2. Create and complete a test Payment Link

1. Open the PayPulse dashboard.
2. In Recovery Queue, select a recommendation whose action is **Send secure payment link** or **Recommend alternate method**.
3. Click its play button.
4. PayPulse creates a real Razorpay test Payment Link and opens hosted checkout.
5. Use a test card published in Razorpay documentation, any future expiry and a random valid CVV.
6. Return to PayPulse and click the verify/shield button on the awaiting-payment row.
7. The server fetches Payment Link status. If paid, the row changes to recovered and the Proof Ledger closes.

This verification route works on localhost and does not require a public webhook URL.

## 3. Optional real webhook

To receive Razorpay webhooks while developing locally, expose port 8000 using a tunnel such as ngrok or Cloudflare Tunnel. Example with ngrok:

```powershell
ngrok http 8000
```

Configure the Razorpay test webhook URL as:

```text
https://YOUR-TUNNEL-DOMAIN/api/webhooks/razorpay
```

Use exactly the same webhook secret in Razorpay Dashboard and `backend/.env`. Subscribe to:

- `payment_link.paid`
- `payment.captured`

PayPulse computes HMAC-SHA256 over the raw request body and compares it with `X-Razorpay-Signature`. Invalid signatures receive HTTP 401. Duplicate webhook bodies are idempotently ignored.

## Safety behavior

- Only `rzp_test_` credentials are accepted.
- PayPulse never accepts or stores card number, CVV or expiry.
- Hosted Razorpay Checkout collects payment details.
- Retry recommendations do not directly debit a card; the MVP schedules the retry.
- LLM output has no access to the execution adapter.
- Payment links are generated only after deterministic guardrails and merchant click approval.
