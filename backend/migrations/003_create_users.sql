-- Create users table for multi-tenant usage
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT,
    email       TEXT NOT NULL,
    google_sub  TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only weekly_plans is per-user; recipes are global (no user_id)
ALTER TABLE weekly_plans 
    ADD COLUMN user_id UUID NOT NULL REFERENCES users(id);
