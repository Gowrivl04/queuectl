"""Worker process implementation."""
from __future__ import annotations

import asyncio
import os
import shlex
import sys
import time
from datetime import timedelta
from typing import Optional, Tuple

import structlog

from .job import Job, JobState
from ..utils.time import utc_now

logger = structlog.get_logger()


class Worker:
    """Job execution worker."""

    def __init__(self):
        """Initialize worker."""
        self.id = None  # Will be set by Queue when registered

    async def _run_command(self, command: str) -> Tuple[int, str, str]:
        """Run a shell command and capture output."""
        start = time.time()
        
        try:
            # On Windows, run through cmd.exe
            if sys.platform == "win32":
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *shlex.split(command),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            
            # Wait for completion and capture output
            stdout, stderr = await process.communicate()
            duration = int((time.time() - start) * 1000)
            
            return (
                process.returncode or 0,
                stdout.decode() if stdout else "",
                stderr.decode() if stderr else ""
            )
            
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return 1, "", str(e)

    async def process_job(self, job: Job) -> None:
        """Process a single job."""
        logger.info(
            "processing_job",
            job_id=job.id,
            command=job.command,
            attempt=job.attempts + 1
        )

        # Run the command
        start = utc_now()
        exit_code, stdout, stderr = await self._run_command(job.command)
        duration = int((utc_now() - start).total_seconds() * 1000)
        
        # Update job status
        job.attempts += 1
        job.stdout = stdout
        job.stderr = stderr
        job.duration_ms = duration
        
        if exit_code == 0:
            job.state = JobState.completed
            job.completed_at = utc_now()
            logger.info(
                "job_completed",
                job_id=job.id,
                duration_ms=duration,
                stdout=stdout.strip()
            )
        else:
            job.last_error = f"Exit code {exit_code}: {stderr}"
            
            if job.attempts >= (job.max_retries + 1):  # +1 because attempts includes initial try
                job.state = JobState.dead
                logger.error(
                    "job_dead",
                    job_id=job.id,
                    attempts=job.attempts,
                    error=job.last_error
                )
            else:
                job.state = JobState.retrying
                logger.info(
                    "job_retry_scheduled",
                    job_id=job.id,
                    attempt=job.attempts,
                    error=job.last_error
                )
                # Schedule retry with exponential backoff
                backoff = min(300, 2 ** (job.attempts - 1))  # Max 5 minute delay
                job.run_at = utc_now() + timedelta(seconds=backoff)
        
        job.updated_at = utc_now()