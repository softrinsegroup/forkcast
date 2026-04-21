CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    instructions TEXT    NOT NULL,
    servings     INTEGER NOT NULL,
    prep_minutes INTEGER NOT NULL,
    cook_minutes INTEGER NOT NULL,
    tags         TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ingredients (
    id        INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name      TEXT    NOT NULL,
    unit      TEXT    NOT NULL,
    amount    REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_plans (
    id         INTEGER PRIMARY KEY,
    timestamp  TEXT NOT NULL,
    recipe_ids TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shopping_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    weekly_plan_id  INTEGER NOT NULL REFERENCES weekly_plans(id) ON DELETE CASCADE,
    ingredient_name TEXT    NOT NULL,
    unit            TEXT    NOT NULL,
    amount          REAL    NOT NULL
);
