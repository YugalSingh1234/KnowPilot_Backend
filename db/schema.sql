-- KnowPilot schema. Safe to re-run. RLS enabled with no policies: only the backend's
-- direct DB connection (table owner) can read/write; Supabase anon/authenticated roles get nothing.
create extension if not exists vector;

create table if not exists organizations (
    id            uuid primary key default gen_random_uuid(),
    name          text not null,
    email         text not null unique,
    password_hash text not null,
    created_at    timestamptz not null default now()
);

create table if not exists assistant_tokens (
    id         uuid primary key default gen_random_uuid(),
    org_id     uuid not null references organizations(id) on delete cascade,
    token      text not null unique,
    is_active  boolean not null default true,
    created_at timestamptz not null default now()
);
create index if not exists ix_assistant_tokens_org_id on assistant_tokens(org_id);

create table if not exists documents (
    id           uuid primary key default gen_random_uuid(),
    org_id       uuid not null references organizations(id) on delete cascade,
    filename     text not null,
    storage_path text not null,
    page_count   integer not null,
    size_bytes   integer not null,
    status       text not null default 'processing',
    created_at   timestamptz not null default now()
);
create index if not exists ix_documents_org_id on documents(org_id);
alter table documents add column if not exists error_message text;
create unique index if not exists ux_documents_org_filename on documents(org_id, filename);

create table if not exists chunks (
    id          uuid primary key default gen_random_uuid(),
    org_id      uuid not null references organizations(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    page_number integer not null,
    chunk_index integer not null,
    content     text not null,
    embedding   vector(768),
    tsv         tsvector generated always as (to_tsvector('simple', content)) stored
);
create index if not exists ix_chunks_org_id on chunks(org_id);
create index if not exists ix_chunks_document_id on chunks(document_id);
create index if not exists ix_chunks_embedding on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists ix_chunks_tsv on chunks using gin (tsv);

-- No question text or personal facts are stored.
create table if not exists question_logs (
    id            uuid primary key default gen_random_uuid(),
    org_id        uuid not null references organizations(id) on delete cascade,
    language      text,
    question_type text,
    status        text not null,
    decision      text,
    latency_ms    integer,
    created_at    timestamptz not null default now()
);
create index if not exists ix_question_logs_org_id on question_logs(org_id);

alter table organizations    enable row level security;
alter table assistant_tokens enable row level security;
alter table documents        enable row level security;
alter table chunks           enable row level security;
alter table question_logs    enable row level security;
