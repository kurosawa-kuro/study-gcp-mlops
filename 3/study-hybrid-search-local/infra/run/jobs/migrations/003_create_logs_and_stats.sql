CREATE TABLE IF NOT EXISTS property_stats (
    property_id BIGINT PRIMARY KEY REFERENCES properties(id) ON DELETE CASCADE,
    impression BIGINT NOT NULL DEFAULT 0,
    click BIGINT NOT NULL DEFAULT 0,
    favorite BIGINT NOT NULL DEFAULT 0,
    inquiry BIGINT NOT NULL DEFAULT 0,
    ctr DOUBLE PRECISION NOT NULL DEFAULT 0,
    fav_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    inquiry_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_logs (
    id BIGSERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    user_id BIGINT,
    result_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    clicked_id BIGINT REFERENCES properties(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_property_stats_updated_at ON property_stats(updated_at);
