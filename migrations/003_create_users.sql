CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    name        TEXT,
    email       TEXT NOT NULL,
    google_sub  TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
