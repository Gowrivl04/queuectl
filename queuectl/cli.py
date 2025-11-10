"""Command-line interface."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional, List

import typer
import structlog
from rich.console import Console
from rich.table import Table

from .config.settings import settings
from .core.job import JobState
from .core.queue import Queue
from .storage.libsql_store import LibSQLStore
from .telemetry.dashboard import run_dashboard

logger = structlog.get_logger()
app = typer.Typer()


@app.command()
def enqueue(
    command: str,
    retries: int = typer.Option(
        settings.max_retries,
        "--retries", "-r",
        help="Number of times to retry the job on failure",
    ),
    priority: int = typer.Option(
        0,
        "--priority", "-p",
        help="Job priority (higher runs first)",
    ),
) -> None:
    """Add a new job to the queue."""
    async def _enqueue() -> None:
        store = LibSQLStore()
        queue = Queue(store=store)
        job = await queue.enqueue(
            command=command,
            max_retries=retries,
            priority=priority,
        )
        logger.info(
            "job_enqueued",
            job_id=job.id,
            command=job.command,
            max_retries=job.max_retries,
            priority=job.priority,
            run_at=job.run_at,
        )
        print(f"Enqueued job {job.id}")

    asyncio.run(_enqueue())


@app.command()
def worker() -> None:
    """Start a job worker."""
    async def _worker() -> None:
        store = LibSQLStore()
        queue = Queue(store=store)
        
        while True:
            await queue.work()
            # Sleep briefly between polls
            await asyncio.sleep(1)

    asyncio.run(_worker())


@app.command()
def dashboard() -> None:
    """Run the web dashboard."""
    asyncio.run(run_dashboard())


@app.command()
def show(job_id: str) -> None:
    """Show details of a specific job."""
    async def _show() -> None:
        store = LibSQLStore()
        queue = Queue(store=store)
        job = await queue.get_job(job_id)
        
        if not job:
            print(f"Job {job_id} not found")
            return
            
        console = Console()
        
        table = Table(show_header=True)
        table.add_column("Field")
        table.add_column("Value")
        
        table.add_row("ID", job.id)
        table.add_row("Command", job.command)
        table.add_row("State", f"[bold]{job.state}[/]")
        table.add_row("Attempts", str(job.attempts))
        table.add_row("Priority", str(job.priority))
        table.add_row("Created", str(job.created_at))
        table.add_row("Updated", str(job.updated_at))
        
        if job.completed_at:
            table.add_row("Completed", str(job.completed_at))
            
        if job.duration_ms:
            table.add_row("Duration", f"{job.duration_ms}ms")
            
        if job.stdout:
            table.add_row("Stdout", job.stdout.strip())
            
        if job.stderr:
            table.add_row("Stderr", f"[red]{job.stderr.strip()}[/]")
            
        if job.last_error:
            table.add_row("Last Error", f"[red]{job.last_error}[/]")
            
        console.print(table)

    asyncio.run(_show())


@app.command()
def stress(
    jobs: int = typer.Option(10, "--jobs", "-n", help="Number of jobs to create"),
    delay_ms: int = typer.Option(100, "--delay", "-d", help="Delay between jobs in ms"),
) -> None:
    """Run a stress test by enqueueing multiple jobs."""
    async def _stress() -> None:
        store = LibSQLStore()
        queue = Queue(store=store)
        console = Console()
        
        with console.status("[bold]Creating jobs...") as status:
            for i in range(jobs):
                job = await queue.enqueue(
                    command=f"echo 'Test job {i+1}'",
                    priority=i % 3,  # Mix different priorities
                )
                console.print(f"Created job {job.id} with priority {job.priority}")
                await asyncio.sleep(delay_ms / 1000)
                
        console.print(f"\n[bold green]Created {jobs} test jobs![/]")

    asyncio.run(_stress())


def main() -> None:
    """Application entry point."""
    app()


if __name__ == "__main__":
    sys.exit(main())
