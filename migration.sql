-- Migration script for existing GatherPix databases
-- Run this if you're upgrading from the old schema

-- Rename firebase_path to cloudinary_public_id
ALTER TABLE photos RENAME COLUMN firebase_path TO cloudinary_public_id;

-- Add resource_type column
ALTER TABLE photos ADD COLUMN IF NOT EXISTS resource_type VARCHAR(10) NOT NULL DEFAULT 'image';

-- Add file_size column
ALTER TABLE photos ADD COLUMN IF NOT EXISTS file_size BIGINT NOT NULL DEFAULT 0;

-- Add greeting and limit columns to events
ALTER TABLE events ADD COLUMN IF NOT EXISTS welcome_message VARCHAR(160);
ALTER TABLE events ADD COLUMN IF NOT EXISTS welcome_tagline VARCHAR(255);
ALTER TABLE events ADD COLUMN IF NOT EXISTS upload_limit_mb INTEGER NOT NULL DEFAULT 200;

-- Widen password_hash for bcrypt
ALTER TABLE users ALTER COLUMN password_hash TYPE VARCHAR(255);
