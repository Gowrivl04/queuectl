-- Worker history table
CREATE TABLE IF NOT EXISTS worker_history (
    worker_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    status TEXT NOT NULL DEFAULT 'processing',
    error TEXT,
    PRIMARY KEY (worker_id, job_id)
);