CREATE TABLE jobs_new (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'processing', 'completed', 'failed', 'retrying', 'dead')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_error TEXT,
    completed_at DATETIME,
    run_at DATETIME,
    priority INTEGER NOT NULL DEFAULT 0,
    stdout TEXT,
    stderr TEXT,
    duration_ms INTEGER,
    locked_by TEXT,
    locked_at DATETIME
);

INSERT INTO jobs_new 
SELECT id, command, state, attempts, max_retries, created_at, updated_at, last_error, completed_at, run_at, priority, stdout, stderr, duration_ms, locked_by, locked_at FROM jobs;

DROP TABLE jobs;
ALTER TABLE jobs_new RENAME TO jobs;

-- Recreate indexes
CREATE INDEX idx_jobs_state ON jobs(state);
CREATE INDEX idx_jobs_run_at ON jobs(run_at);
CREATE INDEX idx_jobs_priority_created ON jobs(priority DESC, created_at ASC);