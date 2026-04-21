CREATE TABLE IF NOT EXISTS ranking_compare_logs (
    id BIGSERIAL PRIMARY KEY,
    search_log_id BIGINT NOT NULL REFERENCES search_logs(id) ON DELETE CASCADE,
    meili_result_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    reranked_result_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    changed_count INTEGER NOT NULL DEFAULT 0,
    top1_changed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ranking_compare_logs_search_log_id
    ON ranking_compare_logs(search_log_id);
CREATE INDEX IF NOT EXISTS idx_ranking_compare_logs_created_at
    ON ranking_compare_logs(created_at DESC);
