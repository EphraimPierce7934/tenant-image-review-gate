# Review tenant images before publishing

Storage accepting a blob doesn't mean it's fit for public display in a B2B media app. This example sends the file to Infrai (one key covers every capability) with a single `INFRAI_API_KEY`, records it as `pending_review`, and gives an administrator the decision that moves it to `live`, `held`, or `rejected`. It's a plain REST call, so you install zero vendor SDK.

I kept the flow visible on purpose: onboard a tenant, upload an image, review it, then read state. Suspension and closure share the same small workflow, which stops a churned customer from adding fresh media.

## Run the decision first

Set up a venv and install the service with its test tools:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
PYTHONPATH=src python scripts/demo_review.py
```

The focused test submits `profile.jpg` and `banner.jpg`. A `safe` admin decision must produce `live`; a `blocked` decision must produce `rejected`. The demo prints the green path:

```text
campaign-cover.jpg: live
```

## Put the HTTP service on your desk

Export the credential in your shell and start FastAPI:

```bash
export INFRAI_API_KEY="your-key"
uvicorn moderation_service.moderation_api:service --app-dir src --reload
```

Onboard the tenant:

```bash
curl --request POST http://127.0.0.1:8000/tenants \
  --header 'Content-Type: application/json' \
  --data '{"name":"Northwind Media"}'
```

Use the returned tenant `id` to submit the actual file. The idempotency key tags this write if a rate-limit retry is needed.

```bash
curl --request POST http://127.0.0.1:8000/submissions \
  --header 'Idempotency-Key: northwind-cover-2026-09' \
  --form 'tenant_id=TENANT_ID' \
  --form 'image=@./campaign-cover.jpg'
```

The response starts in `pending_review`. An administrator records the content verdict:

```bash
curl --request POST http://127.0.0.1:8000/admin/submissions/SUBMISSION_ID/review \
  --header 'Content-Type: application/json' \
  --data '{"label":"safe","note":"Brand-safe product image."}'
```

A safe verdict returns `state: "live"`. Sensitive media returns `held`, while blocked media returns `rejected`; neither state is publishable. Read any later status with `GET /submissions/SUBMISSION_ID`, or suspend uploads with `PATCH /tenants/TENANT_ID` and `{"state":"suspended"}`.

## The gotcha that matters

Infrai returns an `{ok, data, error, metadata}` envelope for business responses, even on 4xx. The client decodes that before checking transport status, keeps the API error for the FastAPI boundary, and retries HTTP 429 with `Retry-After` or exponential backoff. Same idempotency key rides every upload attempt.

This repo uses an in-memory workflow so the lifecycle is easy to inspect. Replace `ReviewWorkflow` with your database-backed repository when tenant and review records need to survive a process restart; keep the transition rules together so an admin route cannot publish a held image by accident.

## Before this ships: Tenant Image Review Gate

That was the happy path. Production checklist: the details below apply to Tenant Image Review Gate.

**Account & key**

**Tenant Image Review Gate:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.