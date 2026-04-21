CREATE TABLE IF NOT EXISTS offline_eval_reports (
    id BIGSERIAL PRIMARY KEY,
    evaluated_queries INTEGER NOT NULL,
    ndcg10_meili DOUBLE PRECISION NOT NULL,
    ndcg10_lgbm DOUBLE PRECISION NOT NULL,
    map_meili DOUBLE PRECISION NOT NULL,
    map_lgbm DOUBLE PRECISION NOT NULL,
    recall20_meili DOUBLE PRECISION NOT NULL,
    recall20_lgbm DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kpi_daily_stats (
    stat_date DATE PRIMARY KEY,
    impressions BIGINT NOT NULL DEFAULT 0,
    clicks BIGINT NOT NULL DEFAULT 0,
    favorites BIGINT NOT NULL DEFAULT 0,
    inquiries BIGINT NOT NULL DEFAULT 0,
    ctr DOUBLE PRECISION NOT NULL DEFAULT 0,
    favorite_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    inquiry_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    cvr DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_adoption_decisions (
    id BIGSERIAL PRIMARY KEY,
    evaluated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    adopt_lgbm BOOLEAN NOT NULL,
    reason TEXT NOT NULL,
    thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_offline_eval_reports_created_at
    ON offline_eval_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_adoption_decisions_evaluated_at
    ON model_adoption_decisions(evaluated_at DESC);
