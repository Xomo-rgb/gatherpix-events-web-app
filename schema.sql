-- GatherPix — PostgreSQL Schema
-- Run this once to set up the database

-- ─── Users (account owners) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(120)  NOT NULL,
    email          VARCHAR(255)  NOT NULL UNIQUE,
    password_hash  CHAR(64)      NOT NULL,
    created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_email ON users(email);

-- ─── Events ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              VARCHAR(255) NOT NULL,
    couple_names      VARCHAR(255),
    event_date        DATE,
    slug              VARCHAR(80)  NOT NULL UNIQUE,
    access_code       VARCHAR(16)  NOT NULL UNIQUE,
    cover_image_url   TEXT,
    welcome_message   VARCHAR(160),
    welcome_tagline   VARCHAR(255),
    upload_limit_mb   INTEGER      NOT NULL DEFAULT 200,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_slug ON events(slug);
CREATE INDEX IF NOT EXISTS idx_user ON events(user_id);

-- ─── Event members ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_members (
    id          SERIAL PRIMARY KEY,
    event_id    INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_event_member ON event_members(event_id);
CREATE INDEX IF NOT EXISTS idx_member_user ON event_members(user_id);

-- ─── Photos ──────────────────────────────────────────────────────────────────
-- NOTE: image_url and firebase_path are kept separate so that migrating
-- to another provider only requires updating image_url values.

CREATE TABLE IF NOT EXISTS photos (
    id                   SERIAL PRIMARY KEY,
    event_id             INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    image_url            TEXT         NOT NULL,
    cloudinary_public_id VARCHAR(500) NOT NULL,
    resource_type        VARCHAR(10)  NOT NULL DEFAULT 'image',
    file_size            BIGINT       NOT NULL DEFAULT 0,
    uploader_name        VARCHAR(120) NOT NULL DEFAULT 'Guest',
    upload_timestamp     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_event ON photos(event_id);
CREATE INDEX IF NOT EXISTS idx_ts ON photos(upload_timestamp);

