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

All routes need `Authorization: Bearer <access_token>` and only ever see the caller's own
organization. There is **no** endpoint that returns PDF files or download links.

### POST /api/documents  → 201
`multipart/form-data` with one field `file` (a single PDF). Indexing happens inside the request,
so the response arrives once the document is `ready` (allow up to ~1 minute).

Response:
```json
{"id": "uuid", "filename": "Scholarship_Policy.pdf", "page_count": 4, "size_bytes": 182344,
 "status": "ready", "chunk_count": 9, "created_at": "2026-11-08T09:03:28.504000+00:00"}
```

Errors, checked in this order:

| Status | code | message (example) |
|---|---|---|
| 400 | `invalid_pdf` | Only PDF files are allowed. / This file could not be opened as a PDF. |
| 413 | `file_too_large` | File is 12.4 MB; the limit is 10 MB. |
| 409 | `document_limit` | You already have 10 of 10 documents. Delete one first. |
| 400 | `encrypted_pdf` | This PDF is password-protected. Please upload an unlocked copy. |
| 400 | `page_limit` | This PDF has 27 pages; the limit is 20. |
| 400 | `text_limit` | This PDF contains too much text; the limit is 300,000 characters. |
| 400 | `no_text` | This looks like a scanned image. Please upload a text-based PDF. |
| 409 | `duplicate_filename` | A document named "Scholarship_Policy.pdf" already exists. |
| 500 | `document_processing_failed` | We couldn't process this PDF. Please try again. |

After `document_processing_failed` the document stays in the list with `status: "failed"`.
It still counts toward the 10-document limit and keeps its filename, so delete it before retrying.

### GET /api/documents  → 200
```json
{
  "documents": [
    {"id": "uuid", "filename": "Scholarship_Policy.pdf", "page_count": 4, "size_bytes": 182344,
     "status": "ready", "chunk_count": 9, "created_at": "2026-11-08T09:03:28.504000+00:00"}
  ],
  "limits": {"max_documents": 10, "max_pages": 20, "max_mb": 10, "used_documents": 1}
}
```
`status` is one of `processing`, `ready`, `failed`. Oldest first.

### DELETE /api/documents/{id}  → 204 (no body)
Removes the document, its chunks and its stored file.
Errors: 404 `not_found` if the id doesn't exist **or** belongs to another organization.

## Assistant

### GET /api/assistant  → 200  (admin, Bearer access_token)
```json
{
  "assistant_url": "http://localhost:5173/a/Xy3...token",
  "token": "Xy3...token",
  "created_at": "2026-11-08T09:03:28.504000+00:00",
  "embed_code": "<iframe src=\"http://localhost:5173/a/Xy3...token\" width=\"100%\" height=\"600\" style=\"border:0;border-radius:12px\" title=\"Sunrise College Assistant\" loading=\"lazy\"></iframe>"
}
```
`assistant_url` is `{PUBLIC_APP_URL}/a/{token}`, so the frontend must serve the route `/a/:token`.
The org name in `title` is HTML-escaped.

### POST /api/assistant/regenerate  → 200  (admin, Bearer access_token)
No body. Revokes the current token and issues a new one; the old link stops working
immediately (its `/info` and `/api/ask` calls return 404 `invalid_token`). Response: same shape
as GET /api/assistant.

### GET /api/assistant/{token}/info  → 200  (public, no login, any origin)
```json
{"org_name": "Sunrise College", "suggested_questions": []}
```
Never returns emails or ids. `suggested_questions` is empty for now.

Errors:
- 404 `invalid_token`: "This assistant link is not active." (unknown, revoked or malformed token)
- 429 `rate_limited`: "Too many questions. Please wait a minute."

Public routes (`/api/assistant/{token}/info`, `/api/ask`) are limited to 20 requests per minute
per visitor IP and 200 requests per minute per assistant token (all visitors combined).

## Ask

### POST /api/ask  → 200  (public, no login, any origin)
Request: `{"assistant_token": "Xy3...token", "question": "Am I eligible for merit-cum-means?"}`
- `question` is trimmed and must be 3-1000 characters.

Response:
```json
{
  "status": "answered",
  "answer": "No, you are not eligible ... (plain text, under ~180 words, in the user's language)",
  "language": "en",
  "question_type": "eligibility",
  "references": [
    {"filename": "NIT_Scholarship_Policy_2025-26.pdf", "page": 1, "snippet": "1. Merit-cum-Means Scholarship ..."}
  ],
  "decision": {
    "outcome": "NOT_ELIGIBLE",
    "score": 80,
    "booleans": [
      {"label": "Annual family income", "result": "TRUE", "user_value": 650000,
       "required_value": "₹8,00,000", "source": {"filename": "NIT_Scholarship_Policy_2025-26.pdf", "page": 1}}
    ],
    "missing_facts": [],
    "timings": [{"decision": "boolean", "start_ms": 0.4, "end_ms": 1.2, "error": null}]
  },
  "trace": [{"step": "language", "kind": "system1", "ms": 0.1}, {"step": "generate_answer", "kind": "llm", "ms": 2140.5}]
}
```

| Field | Values |
|---|---|
| `status` | `answered`; `no_answer` (fixed message, `references` is `[]`: out of scope or low retrieval scores, with no LLM call; or the LLM reports the documents don't cover it); `passages_only` (AI service busy: `answer` starts with "The AI service is busy; here are the most relevant passages:" and `references` holds the top 3 passages) |
| `language` | `en`, `hi`, `hinglish` |
| `question_type` | `direct`, `policy`, `procedural`, `eligibility`, `comparison`, `out_of_scope` |
| `decision` | `null` unless the question is an eligibility question and rules were found |
| `decision.outcome` | `ELIGIBLE`, `NOT_ELIGIBLE`, `NEEDS_MORE_INFO` (then `missing_facts` lists what to ask) |
| `booleans[].result` | `TRUE`, `FALSE`, `UNKNOWN` |
| `decision.score` | 0-100: weighted share of conditions met (UNKNOWN counts half) |
| `trace[].kind` | `system1`, `retrieval`, `llm`, `fallback` |

The decision is computed in Python; the answer text never contradicts it.

Errors: 404 `invalid_token`, 422 `validation_error`, 429 `rate_limited`, 503 `service_busy` ("Please try again in a moment.", database briefly unreachable after one retry; any route can return it).

## Usage

### GET /api/usage  → 200  (admin, Bearer access_token)
Counts for the caller's organization only. Question text and personal facts are never stored.
```json
{
  "total_questions": 42,
  "by_status": {"answered": 35, "no_answer": 6, "passages_only": 1},
  "by_question_type": {"eligibility": 12, "direct": 20, "policy": 10},
  "by_language": {"en": 30, "hinglish": 10, "hi": 2}
}
```
Keys appear only when their count is above zero.
