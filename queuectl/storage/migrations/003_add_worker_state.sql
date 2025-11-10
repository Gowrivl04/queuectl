-- Recreate workers table with updated schema
CREATE TABLE workers_new (
    id TEXT PRIMARY KEY,
    pid INTEGER NOT NULL,
    hostname TEXT NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    state TEXT NOT NULL DEFAULT 'active',
    last_job_id TEXT,
    last_job_at DATETIME
);

INSERT INTO workers_new 
SELECT id, pid, hostname, started_at, last_heartbeat_at, status, NULL, NULL 
FROM workers;

DROP TABLE workers;
ALTER TABLE workers_new RENAME TO workers;

-- Recreate index
CREATE INDEX idx_workers_heartbeat ON workers(last_heartbeat_at);