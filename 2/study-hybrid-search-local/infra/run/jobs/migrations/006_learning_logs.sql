ALTER TABLE search_logs
ADD COLUMN IF NOT EXISTS actioned_id BIGINT REFERENCES properties(id);

ALTER TABLE search_logs
ADD COLUMN IF NOT EXISTS action_type TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_search_logs_action_type'
    ) THEN
        ALTER TABLE search_logs
        ADD CONSTRAINT chk_search_logs_action_type
        CHECK (action_type IN ('click', 'favorite', 'inquiry') OR action_type IS NULL);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_search_logs_action_type ON search_logs(action_type);
