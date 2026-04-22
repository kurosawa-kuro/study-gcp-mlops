CREATE TABLE IF NOT EXISTS property_embeddings (
    property_id BIGINT PRIMARY KEY REFERENCES properties(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    embedding DOUBLE PRECISION[] NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE search_logs
ADD COLUMN IF NOT EXISTS me5_scores JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE property_features
ADD COLUMN IF NOT EXISTS me5_score DOUBLE PRECISION NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_property_embeddings_updated_at ON property_embeddings(updated_at);
