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
to be filled

## Ask
to be filled

## Usage
to be filled
