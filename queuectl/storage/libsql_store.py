"""LibSQL storage implementation."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import asyncio
from pathlib import Path
import contextlib

import libsql_client
from pydantic import BaseModel

from ..core.job import Job, JobState
from ..utils.time import utc_now


class LibSQLStore:
    """Storage layer using LibSQL."""
    
    def __init__(self, dsn: Optional[str] = None):
        """Initialize LibSQL storage with optional DSN."""
        self.dsn = dsn or os.getenv("QUEUECTL_LIBSQL_DSN", "file:local.db")
        self._client: Optional[libsql_client.Client] = None
        self._lock = asyncio.Lock()
    
    async def get_client(self) -> libsql_client.Client:
        """Get or create LibSQL client."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = libsql_client.create_client(
                        url=self.dsn,
                        auth_token=None
                    )
                    await self._migrate()
        return self._client

    async def _migrate(self) -> None:
        """Apply all migrations in order."""
        # Create migrations table if it doesnt exist
        await (await self.get_client()).execute(
            "CREATE TABLE IF NOT EXISTS migrations ("
            "id TEXT PRIMARY KEY,"
            "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        migrations_dir = Path(__file__).parent / "migrations"
        for filepath in sorted(migrations_dir.glob("*.sql")):
            migration_id = filepath.stem
            
            # Check if migration was already applied
            result = await (await self.get_client()).execute(
                "SELECT id FROM migrations WHERE id = ?",
                [migration_id]
            )
            if result.rows:
                continue
                
            # Apply migration
            sql = filepath.read_text()
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            
            for statement in statements:
                await (await self.get_client()).execute(statement)
                
            # Record migration as applied
            await (await self.get_client()).execute(
                "INSERT INTO migrations (id) VALUES (?)",
                [migration_id]
            )

        # Clean up stale workers now that tables exist    
        await self._cleanup_stale_workers()

    async def enqueue(self, job: Job) -> None:
        """Add a new job to the queue."""
        sql = """
            INSERT INTO jobs (
                id, command, state, attempts, max_retries, created_at,
                run_at, priority, updated_at, locked_by, locked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await (await self.get_client()).execute(
            sql,
            [
                job.id,
                job.command,
                job.state.value,
                job.attempts,
                job.max_retries,
                job.created_at.isoformat(),
                job.run_at.isoformat() if job.run_at else None,
                job.priority,
                job.updated_at.isoformat(),
                job.locked_by,
                job.locked_at.isoformat() if job.locked_at else None,
            ]
        )

    async def dequeue(self, worker_id: str) -> Optional[Job]:
        """Atomically fetch and lock the next available job."""
        now = utc_now()
        
        # First try to find a job
        result = await (await self.get_client()).execute("""
            SELECT * FROM jobs 
            WHERE (state = 'pending' OR state = 'retrying')
            AND (run_at IS NULL OR run_at <= ?)
            AND (locked_by IS NULL OR locked_at < ?) 
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        """, [now.isoformat(), (now - timedelta(minutes=5)).isoformat()])
        
        if not result.rows:
            return None
            
        job_data = dict(zip(result.columns, result.rows[0]))
        job_id = job_data["id"]
        
        # Lock the job
        await (await self.get_client()).execute("""
            UPDATE jobs 
            SET state = 'processing',
                locked_by = ?,
                locked_at = ?,
                updated_at = ?
            WHERE id = ?
            AND (state = 'pending' OR state = 'retrying')
            AND (locked_by IS NULL OR locked_at < ?)
        """, [
            worker_id,
            now.isoformat(),
            now.isoformat(),
            job_id,
            (now - timedelta(minutes=5)).isoformat()
        ])
        
        # Verify we got the lock
        result = await (await self.get_client()).execute(
            "SELECT locked_by FROM jobs WHERE id = ?",
            [job_id]
        )
        if not result.rows or result.rows[0][0] != worker_id:
            return None  # Lost the race
            
        return Job(
            id=job_data["id"],
            command=job_data["command"],
            state=JobState(job_data["state"]),
            attempts=job_data["attempts"],
            max_retries=job_data["max_retries"],
            created_at=datetime.fromisoformat(job_data["created_at"]),
            updated_at=datetime.fromisoformat(job_data["updated_at"]),
            last_error=job_data["last_error"],
            completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data["completed_at"] else None,
            run_at=datetime.fromisoformat(job_data["run_at"]) if job_data["run_at"] else None,
            priority=job_data["priority"],
            stdout=job_data["stdout"],
            stderr=job_data["stderr"],
            duration_ms=job_data["duration_ms"],
            locked_by=job_data["locked_by"],
            locked_at=datetime.fromisoformat(job_data["locked_at"]) if job_data["locked_at"] else None,
        )

    async def update_job(self, job: Job) -> None:
        """Update job status and related fields."""
        sql = """
            UPDATE jobs SET
                state = ?,
                attempts = ?,
                updated_at = ?,
                last_error = ?,
                completed_at = ?,
                run_at = ?,
                stdout = ?,
                stderr = ?,
                duration_ms = ?,
                locked_by = NULL,
                locked_at = NULL
            WHERE id = ?
            AND (locked_by = ? OR locked_by IS NULL)
        """
        # Convert float timestamps to ISO format datetime strings
        def format_timestamp(ts):
            if ts is None:
                return None
            if isinstance(ts, (int, float)):
                ts = datetime.fromtimestamp(ts, timezone.utc)
            if isinstance(ts, datetime):
                return ts.isoformat()
            return str(ts)
            
        await (await self.get_client()).execute(
            sql,
            [
                job.state.value,
                job.attempts,
                format_timestamp(job.updated_at),
                job.last_error,
                format_timestamp(job.completed_at),
                format_timestamp(job.run_at),
                job.stdout,
                job.stderr,
                job.duration_ms,
                job.id,
                job.locked_by
            ]
        )

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        result = await (await self.get_client()).execute(
            "SELECT * FROM jobs WHERE id = ?",
            [job_id]
        )
        if not result.rows:
            return None
            
        job_data = dict(zip(result.columns, result.rows[0]))
        return Job(
            id=job_data["id"],
            command=job_data["command"],
            state=JobState(job_data["state"]),
            attempts=job_data["attempts"],
            max_retries=job_data["max_retries"],
            created_at=datetime.fromisoformat(job_data["created_at"]),
            updated_at=datetime.fromisoformat(job_data["updated_at"]),
            last_error=job_data["last_error"],
            completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data["completed_at"] else None,
            run_at=datetime.fromisoformat(job_data["run_at"]) if job_data["run_at"] else None,
            priority=job_data["priority"],
            stdout=job_data["stdout"],
            stderr=job_data["stderr"],
            duration_ms=job_data["duration_ms"],
            locked_by=job_data["locked_by"],
            locked_at=datetime.fromisoformat(job_data["locked_at"]) if job_data["locked_at"] else None,
        )

    async def list_jobs(
        self, state: Optional[JobState] = None, limit: int = 100
    ) -> List[Job]:
        """List jobs, optionally filtered by state."""
        sql = "SELECT * FROM jobs"
        params: List[Any] = []
        
        if state:
            sql += " WHERE state = ?"
            params.append(state.value)
            
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        result = await (await self.get_client()).execute(sql, params)
        
        jobs = []
        for row in result.rows:
            job_data = dict(zip(result.columns, row))
            jobs.append(Job(
                id=job_data["id"],
                command=job_data["command"],
                state=JobState(job_data["state"]),
                attempts=job_data["attempts"],
                max_retries=job_data["max_retries"],
                created_at=datetime.fromisoformat(job_data["created_at"]),
                updated_at=datetime.fromisoformat(job_data["updated_at"]),
                last_error=job_data["last_error"],
                completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data["completed_at"] else None,
                run_at=datetime.fromisoformat(job_data["run_at"]) if job_data["run_at"] else None,
                priority=job_data["priority"],
                stdout=job_data["stdout"],
                stderr=job_data["stderr"],
                duration_ms=job_data["duration_ms"],
                locked_by=job_data["locked_by"],
                locked_at=datetime.fromisoformat(job_data["locked_at"]) if job_data["locked_at"] else None,
            ))
        return jobs

    async def register_worker(self, worker_id: str, pid: int, hostname: str) -> None:
        """Register a new worker."""
        sql = """
            INSERT INTO workers (id, pid, hostname)
            VALUES (?, ?, ?)
        """
        await (await self.get_client()).execute(sql, [worker_id, pid, hostname])

    async def heartbeat_worker(self, worker_id: str) -> None:
        """Update worker heartbeat."""
        sql = """
            INSERT OR REPLACE INTO workers (
                id, pid, hostname, last_heartbeat_at, started_at
            ) SELECT 
                id, pid, hostname, ?, started_at
            FROM workers 
            WHERE id = ?
        """
        await (await self.get_client()).execute(sql, [utc_now().isoformat(), worker_id])

    async def deregister_worker(self, worker_id: str) -> None:
        """Remove a worker registration."""
        sql = "DELETE FROM workers WHERE id = ?"
        await (await self.get_client()).execute(sql, [worker_id])

    async def get_config(self, key: str) -> Optional[str]:
        """Get a configuration value."""
        sql = "SELECT value FROM config WHERE key = ?"
        result = await (await self.get_client()).execute(sql, [key])
        row = await result.fetchone()
        if row:
            return row[0]
        return None

    async def _cleanup_stale_workers(self) -> None:
        """Clean up stale workers and their jobs."""
        # Workers inactive for more than 30 seconds are considered dead
        cutoff_time = (utc_now() - timedelta(seconds=30)).isoformat()
        
        # First get list of stale workers
        result = await (await self.get_client()).execute("""
            SELECT id FROM workers
            WHERE last_heartbeat_at < ? AND state = 'active'
        """, [cutoff_time])
        
        for row in result.rows:
            worker_id = row[0]
            await self.cleanup_worker_jobs(worker_id)
            # Update worker state to 'dead'
            await (await self.get_client()).execute("""
                UPDATE workers SET state = 'dead'
                WHERE id = ?
            """, [worker_id])
    
    async def cleanup_worker_jobs(self, worker_id: str) -> None:
        """Clean up jobs assigned to a worker."""
        # Get jobs locked by this worker
        result = await (await self.get_client()).execute("""
            SELECT id FROM jobs
            WHERE locked_by = ? AND state = 'processing'
        """, [worker_id])
        
        # Reset jobs to pending state
        for row in result.rows:
            job_id = row[0]
            await (await self.get_client()).execute("""
                UPDATE jobs 
                SET state = 'pending',
                    locked_by = NULL,
                    locked_at = NULL,
                    updated_at = ?
                WHERE id = ?
            """, [utc_now().isoformat(), job_id])

    async def get_active_workers(self) -> List[Dict[str, str]]:
        """Get a list of active workers."""
        sql = """
            SELECT id, pid, hostname, last_heartbeat_at, state 
            FROM workers 
            WHERE last_heartbeat_at > ? AND state = 'active'
        """
        # Workers inactive for more than 30 seconds are considered dead
        cutoff_time = (utc_now() - timedelta(seconds=30)).isoformat()
        result = await (await self.get_client()).execute(sql, [cutoff_time])
        return [
            {
                'id': row[0],
                'pid': row[1],
                'hostname': row[2],
                'last_heartbeat_at': row[3],
                'state': row[4]
            }
            for row in result.rows
        ]

    async def set_config(self, key: str, value: str) -> None:
        """Set a configuration value."""
        sql = """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (key) DO UPDATE
            SET value = excluded.value,
                updated_at = excluded.updated_at
        """
        await (await self.get_client()).execute(
            sql,
            [key, value, utc_now().isoformat()]
        )

    async def reset_database(self) -> None:
        """Reset the database to a clean state."""
        # Drop existing tables
        tables = ["jobs", "workers", "migrations", "config", "worker_history"]
        for table in tables:
            try:
                await (await self.get_client()).execute(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass
        
        # Reset client to force new migrations
        self._client = None
