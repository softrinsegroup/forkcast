CREATE TABLE IF NOT EXISTS prompts (
    id      SERIAL PRIMARY KEY,
    type    VARCHAR(50) NOT NULL,
    prompt  TEXT NOT NULL,
    version INTEGER NOT NULL,
    active  BOOLEAN NOT NULL DEFAULT FALSE,
    model   VARCHAR(100),
    notes   TEXT,
    created_at TIMESTAMPTZ NOT NULL
)
