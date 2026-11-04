CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.episodes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace       text NOT NULL,
    agent_id        text,
    run_id          text,
    trace_id        text,
    kind            text NOT NULL,
    content         jsonb NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      timestamptz
);

CREATE TABLE IF NOT EXISTS public.memories (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace       text NOT NULL,
    subject         text,
    content         jsonb NOT NULL,
    text            text NOT NULL,
    embedding       vector,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    valid_to        timestamptz,
    created_at      timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      timestamptz
);