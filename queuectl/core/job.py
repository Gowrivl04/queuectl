"""Job definition and states."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from ..utils.time import utc_now


class JobState(str, Enum):
    """Job execution states."""

    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    retrying = "retrying"
    dead = "dead"


class Job:
    """A job in the queue."""

    def __init__(
        self,
        command: str,
        max_retries: int = 3,
        priority: int = 0,
        run_at: Optional[datetime] = None,
        id: Optional[str] = None,
        state: JobState = JobState.pending,
        attempts: int = 0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        last_error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        duration_ms: Optional[int] = None,
        locked_by: Optional[str] = None,
        locked_at: Optional[datetime] = None,
    ):
        """Initialize a job."""
        now = utc_now()
        self.id = id or str(uuid.uuid4())
        self.command = command
        self.state = state
        self.attempts = attempts
        self.max_retries = max_retries
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self.last_error = last_error
        self.completed_at = completed_at
        self.run_at = run_at
        self.priority = priority
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms
        self.locked_by = locked_by
        self.locked_at = locked_at