# AskMyData Developer API

## Overview

The AskMyData Developer API enables authorized external applications to interact with the platform programmatically. It provides secure access to datasets, analytics, natural-language questions, and real-time webhook notifications.

**Base URL:** `https://your-domain.com/api/v1/public/`

---

## Authentication

All API requests require a valid API key sent via the `Authorization` header:

```
Authorization: Bearer ask_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

API keys are created through the developer dashboard at `/settings/developer` or through the management API.

### Key format

| Environment | Prefix       | Example                                          |
|-------------|--------------|--------------------------------------------------|
| Production  | `ask_live_`  | `ask_live_Kx7mP9qR2sT4uV6wX8yZ0bC3dE5fG7hJ`    |
| Development | `ask_test_`  | `ask_test_Kx7mP9qR2sT4uV6wX8yZ0bC3dE5fG7hJ`    |

### Security

- API keys are hashed with SHA-256 before storage. The raw key is shown only once at creation.
- Never include API keys in URL query parameters.
- Never commit API keys to version control.
- Rotate keys periodically and revoke keys that are no longer needed.

---

## API Scopes

Each API key is granted specific scopes that determine what operations it can perform.

| Scope               | Description                                    |
|----------------------|------------------------------------------------|
| `datasets:read`     | List and view dataset metadata                 |
| `datasets:write`    | Upload and manage datasets                     |
| `analytics:read`    | View saved analytics results                   |
| `analytics:run`     | Execute structured analytics queries           |
| `analytics:question`| Ask natural-language questions about datasets   |
| `reports:read`      | View report metadata                           |
| `workspace:read`    | View workspace information                     |
| `webhooks:read`     | View webhook configurations                    |
| `webhooks:write`    | Create and manage webhooks                     |

---

## Rate Limits

Rate limits are applied per workspace and per API key per hour.

| Plan       | Requests/Hour | Analytics/Hour |
|------------|---------------|----------------|
| Free       | 100           | 20             |
| Pro        | 1,000         | 200            |
| Team       | 5,000         | 1,000          |
| Enterprise | 10,000        | 2,000          |

Rate limit headers are returned with every response:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 994
X-RateLimit-Reset: 1696406400
```

When the limit is exceeded, the API returns `429 Too Many Requests`.

---

## Response Format

### Success

```json
{
  "success": true,
  "data": { ... },
  "request_id": "abc123-def456-..."
}
```

### Error

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_SCOPE",
    "message": "The API key does not have the required permission."
  },
  "request_id": "abc123-def456-..."
}
```

### Common Error Codes

| HTTP Status | Code                         | Description                                    |
|-------------|------------------------------|------------------------------------------------|
| 401         | `INVALID_API_KEY`           | API key is invalid, revoked, or malformed      |
| 401         | `API_KEY_EXPIRED`           | API key has passed its expiration date          |
| 401         | `API_KEY_INACTIVE`          | Key owner lost workspace access                |
| 403         | `INSUFFICIENT_SCOPE`        | API key lacks the required scope               |
| 403         | `FEATURE_NOT_AVAILABLE`     | Plan does not include developer API access      |
| 403         | `WORKSPACE_PERMISSION_CHANGED` | Workspace role no longer allows this action |
| 404         | `DATASET_NOT_FOUND`         | Dataset does not exist or is not accessible     |
| 422         | `VALIDATION_ERROR`          | Request body failed validation                 |
| 422         | `INVALID_ANALYTICS_REQUEST` | Analytics operation is invalid                 |
| 429         | `RATE_LIMITED`              | Request limit exceeded                         |
| 429         | `USAGE_LIMIT_REACHED`       | Workspace usage limit exceeded                 |
| 500         | `INTERNAL_ERROR`            | Unexpected server error                        |

---

## Endpoints

### List Datasets

```
GET /api/v1/public/datasets
```

**Required scope:** `datasets:read`

**Response:**

```json
{
  "success": true,
  "data": {
    "datasets": [
      {
        "dataset_id": "demo-placement",
        "dataset_name": "Demo Placement Dataset",
        "original_filename": "placement.csv",
        "row_count": 215,
        "column_count": 12,
        "status": "active",
        "validation_status": "valid",
        "is_builtin": true,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00"
      }
    ]
  },
  "request_id": "..."
}
```

### Get Dataset

```
GET /api/v1/public/datasets/{dataset_id}
```

**Required scope:** `datasets:read`

### Get Workspace

```
GET /api/v1/public/workspace
```

**Required scope:** `workspace:read`

### Run Analytics Query

```
POST /api/v1/public/analytics/query
```

**Required scope:** `analytics:run`

**Request body:**

```json
{
  "operation": "placement_by_internship",
  "dataset_id": "demo-placement",
  "column": null,
  "group_by": null
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "operation": "placement_by_internship",
    "dataset_id": "demo-placement",
    "result": { ... }
  },
  "request_id": "..."
}
```

### Ask a Natural Language Question

```
POST /api/v1/public/analytics/question
```

**Required scope:** `analytics:question`

**Request body:**

```json
{
  "dataset_id": "demo-placement",
  "question": "What is the placement rate for students with internship experience?"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "analysis": { ... },
    "explanation": "Based on the data...",
    "visualization": null
  },
  "request_id": "..."
}
```

> **Note:** AI-generated explanations supplement real analytics results. Numerical results always come from the actual data engine, not from the AI.

---

## API Key Management

These endpoints require session authentication (not API key auth) and workspace admin privileges.

### Create API Key

```
POST /api/v1/developer/api-keys
```

```json
{
  "workspace_id": "ws-xxx",
  "name": "Production Integration",
  "scopes": ["datasets:read", "analytics:run"],
  "expires_at": "2027-01-01T00:00:00Z"
}
```

### List API Keys

```
GET /api/v1/developer/api-keys?workspace_id=ws-xxx
```

### Revoke API Key

```
POST /api/v1/developer/api-keys/{key_id}/revoke?workspace_id=ws-xxx
```

### Rotate API Key

```
POST /api/v1/developer/api-keys/{key_id}/rotate
```

```json
{
  "workspace_id": "ws-xxx",
  "grace_seconds": 3600
}
```

### View Usage

```
GET /api/v1/developer/usage?workspace_id=ws-xxx&since=2026-09-01T00:00:00Z
```

---

## Webhooks

AskMyData can send real-time HTTP notifications when events occur.

### Supported Events

| Event                        | Description                          |
|------------------------------|--------------------------------------|
| `dataset.created`           | A dataset was uploaded               |
| `dataset.updated`           | A dataset was modified               |
| `dataset.deleted`           | A dataset was deleted                |
| `analytics.completed`       | An analytics query succeeded         |
| `analytics.failed`          | An analytics query failed            |
| `report.created`            | A report was generated               |
| `workspace.member_added`    | A member joined the workspace        |
| `workspace.member_removed`  | A member left the workspace          |
| `subscription.updated`      | Subscription plan changed            |
| `subscription.canceled`     | Subscription was canceled            |
| `usage.limit_reached`       | A usage limit was reached            |
| `security.event`            | A security-relevant event occurred   |
| `webhook.test`              | A test event was sent                |

### Webhook Payload

```json
{
  "id": "evt_abc123",
  "type": "analytics.completed",
  "created_at": "2026-10-01T12:00:00+00:00",
  "workspace_id": "ws-xxx",
  "data": {
    "dataset_id": "demo-placement",
    "operation": "placement_by_internship",
    "api_key_id": "key-xxx"
  }
}
```

### Signature Verification

Every webhook request includes a signature header:

```
X-AskMyData-Signature: t=1696161600,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
```

To verify:

1. Extract the timestamp (`t`) and signature (`v1`) from the header.
2. Concatenate the timestamp, a dot (`.`), and the raw request body.
3. Compute HMAC-SHA256 using your webhook secret.
4. Compare the computed signature with `v1`.

**Python example:**

```python
import hashlib
import hmac

def verify_webhook(payload: bytes, signature_header: str, secret: str) -> bool:
    parts = dict(kv.split("=", 1) for kv in signature_header.split(","))
    timestamp = parts["t"]
    expected = parts["v1"]
    computed = hmac.new(
        secret.encode(), timestamp.encode() + b"." + payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, expected)
```

### Additional Headers

| Header                      | Description                      |
|-----------------------------|----------------------------------|
| `X-AskMyData-Event`        | The event type                   |
| `X-AskMyData-Delivery-ID`  | Unique delivery identifier       |
| `X-AskMyData-Timestamp`    | UNIX timestamp of the request    |

### Retry Behavior

Failed deliveries are retried up to 3 times with exponential backoff:

| Attempt | Delay   |
|---------|---------|
| 1       | —       |
| 2       | 250ms   |
| 3       | 500ms   |

After all attempts fail, the delivery is marked as failed and the webhook's failure counter increments.

### Idempotency

Each delivery has a unique `event_id`. If a webhook endpoint for a specific `event_id` has already been queued, duplicate delivery is suppressed.

### SSRF Protection

Webhook URLs are validated to prevent Server-Side Request Forgery:

- Only HTTPS URLs on port 443 are accepted.
- URLs pointing to localhost, private IP ranges, link-local, cloud metadata endpoints, or internal hosts are rejected.
- DNS resolution is checked to ensure the target resolves to a public IP.

### Webhook Management

| Method   | Endpoint                                                     | Description                |
|----------|--------------------------------------------------------------|----------------------------|
| `GET`    | `/api/v1/developer/webhooks?workspace_id=...`               | List webhooks              |
| `POST`   | `/api/v1/developer/webhooks`                                | Create webhook             |
| `PATCH`  | `/api/v1/developer/webhooks/{id}`                           | Update webhook             |
| `DELETE` | `/api/v1/developer/webhooks/{id}?workspace_id=...`          | Delete webhook             |
| `POST`   | `/api/v1/developer/webhooks/{id}/rotate-secret?workspace_id=...` | Rotate signing secret |
| `POST`   | `/api/v1/developer/webhooks/{id}/test?workspace_id=...`     | Send test event            |
| `GET`    | `/api/v1/developer/webhooks/{id}/deliveries?workspace_id=...` | View delivery history    |

---

## Code Examples

### cURL — List Datasets

```bash
curl -H "Authorization: Bearer ask_live_YOUR_KEY_HERE" \
  https://your-domain.com/api/v1/public/datasets
```

### cURL — Run Analytics

```bash
curl -X POST \
  -H "Authorization: Bearer ask_live_YOUR_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"operation":"placement_by_internship","dataset_id":"demo-placement"}' \
  https://your-domain.com/api/v1/public/analytics/query
```

### Python

```python
import requests

API_KEY = "ask_live_YOUR_KEY_HERE"
BASE = "https://your-domain.com/api/v1/public"

# List datasets
datasets = requests.get(f"{BASE}/datasets", headers={
    "Authorization": f"Bearer {API_KEY}",
}).json()

print(datasets["data"]["datasets"])

# Ask a question
answer = requests.post(f"{BASE}/analytics/question", headers={
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}, json={
    "dataset_id": "demo-placement",
    "question": "What percentage of students with internships got placed?",
}).json()

print(answer["data"])
```

### JavaScript / Node.js

```javascript
const API_KEY = "ask_live_YOUR_KEY_HERE";
const BASE = "https://your-domain.com/api/v1/public";

// List datasets
const datasets = await fetch(`${BASE}/datasets`, {
  headers: { Authorization: `Bearer ${API_KEY}` },
}).then(r => r.json());

console.log(datasets.data.datasets);

// Run analytics
const result = await fetch(`${BASE}/analytics/query`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    operation: "placement_by_internship",
    dataset_id: "demo-placement",
  }),
}).then(r => r.json());

console.log(result.data);
```

---

## Environment Variables

| Variable               | Purpose                                        | Required |
|------------------------|------------------------------------------------|----------|
| `WEBHOOK_ENCRYPTION_KEY` | Fernet key for encrypting webhook secrets     | Yes (production) |
| `APP_ENV`              | `production` or `development` — controls key prefix | Yes |

Generate a webhook encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Security Best Practices

1. **Use HTTPS** for all API requests.
2. **Store keys securely** — use environment variables or a secrets manager.
3. **Use least-privilege scopes** — only grant the scopes your application needs.
4. **Rotate keys periodically** — use the rotation endpoint with a grace period.
5. **Verify webhook signatures** — always validate the HMAC signature before processing events.
6. **Monitor usage** — check the developer dashboard for unusual activity.
7. **Set expiration dates** — API keys should expire; rotate before expiry.
