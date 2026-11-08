# API Contract

The frontend repo depends on these shapes. Record every response-shape change here.

## Auth

All errors: `{"error": {"code": "...", "message": "..."}}`. Admin routes need
`Authorization: Bearer <access_token>`. There is no logout endpoint: the frontend logs out by
deleting its stored token. Tokens expire after `JWT_EXPIRE_MINUTES` (default 720).

### POST /api/auth/register  → 201
Request: `{"org_name": "Sunrise College", "email": "admin@sunrise.edu", "password": "min8chars"}`
- `org_name` 2-100 chars, `email` valid (stored lowercase), `password` 8-72 bytes.
- Also creates the organization's first active assistant token.

Response:
```json
{"access_token": "eyJ...", "org": {"id": "uuid", "name": "Sunrise College", "email": "admin@sunrise.edu"}}
```
Errors: 409 `email_exists`, 422 `validation_error`.

### POST /api/auth/login  → 200
Request: `{"email": "admin@sunrise.edu", "password": "min8chars"}`
Response: same as register.
Errors: 401 `invalid_credentials` (same for wrong email or wrong password).

### GET /api/auth/me  → 200
Response: `{"id": "uuid", "name": "Sunrise College", "email": "admin@sunrise.edu"}`
Errors: 401 `unauthorized` (missing, expired, invalid, or non-admin token).

## Documents
to be filled

## Assistant
to be filled

## Ask
to be filled

## Usage
to be filled
