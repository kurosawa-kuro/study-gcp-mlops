ALTER TABLE properties
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS property_features (
    property_id BIGINT PRIMARY KEY REFERENCES properties(id) ON DELETE CASCADE,
    price INTEGER NOT NULL,
    walk_min INTEGER NOT NULL,
    age INTEGER NOT NULL,
    area DOUBLE PRECISION NOT NULL,
    photo_count INTEGER NOT NULL DEFAULT 0,
    ctr DOUBLE PRECISION NOT NULL DEFAULT 0,
    fav_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    inquiry_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    popularity_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS batch_job_logs (
    id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,
    processed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_property_features_updated_at ON property_features(updated_at);
CREATE INDEX IF NOT EXISTS idx_property_features_popularity ON property_features(popularity_score DESC);
CREATE INDEX IF NOT EXISTS idx_batch_job_logs_job_name_started_at ON batch_job_logs(job_name, started_at DESC);
