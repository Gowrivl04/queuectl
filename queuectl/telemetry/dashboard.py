"""Dashboard data and analytics."""
from __future__ import annotations

from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional, Tuple

import aiohttp
from aiohttp import web
import structlog

from ..config.settings import settings
from ..core.job import JobState
from ..storage.libsql_store import LibSQLStore
from ..utils.time import utc_now

logger = structlog.get_logger()

class Dashboard:
    """Provides queue analytics and insights."""

    def __init__(self, store: LibSQLStore):
        """Initialize dashboard with storage."""
        self.store = store

    async def get_job_stats(
        self, window: timedelta = timedelta(hours=24)
    ) -> Dict[str, int]:
        """Get job statistics for time window."""
        stats = {f"jobs_{state.value}": 0 for state in JobState}
        stats["retried_jobs"] = 0
        stats["avg_attempts"] = 0
        
        try:
            sql = """
                SELECT
                    state,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration,
                    SUM(CASE WHEN attempts > 1 THEN 1 ELSE 0 END) as retried_jobs,
                    AVG(attempts) as avg_attempts
                FROM jobs
                WHERE created_at > ?
                GROUP BY state
            """
            cutoff = utc_now() - window
            result = await (await self.store.client).execute(
                sql, [cutoff.isoformat(), cutoff.isoformat()]
            )
            
            total_retried = 0
            total_attempts = 0
            total_jobs = 0
            
            if result.rows:
                for row in result.rows:
                    if row[0]:  # state column
                        stats[f"jobs_{row[0]}"] = row[1]  # count
                        if row[2]:  # avg_duration
                            stats[f"avg_duration_{row[0]}"] = int(row[2])
                        
                        # Accumulate totals
                        total_retried += row[3] or 0  # retried_jobs
                        total_attempts += (row[1] * (row[4] or 1))  # count * avg_attempts
                        total_jobs += row[1]
                
                stats["retried_jobs"] = total_retried
                stats["avg_attempts"] = round(total_attempts / total_jobs, 2) if total_jobs > 0 else 0.0
                    
        except Exception as e:
            logger.error("error_getting_stats", error=str(e))
            
        return stats

    async def get_active_workers(self) -> List[Dict[str, str]]:
        """Get list of currently active workers."""
        workers = []
        try:
            cutoff = utc_now() - timedelta(minutes=5)
            sql = """
                SELECT id, pid, hostname, started_at, last_heartbeat
                FROM workers
                WHERE last_heartbeat > ?
            """
            result = await (await self.store.client).execute(
                sql, [cutoff.isoformat()]
            )
            
            for row in result.rows:
                workers.append({
                    "id": row[0],
                    "pid": str(row[1]),
                    "hostname": row[2],
                    "started_at": row[3],
                    "last_heartbeat": row[4]
                })
        except Exception as e:
            logger.error("error_getting_workers", error=str(e))
            
        return workers

    async def get_job_history(
        self,
        window: timedelta = timedelta(hours=24),
        interval: timedelta = timedelta(minutes=5)
    ) -> List[Dict[str, any]]:
        """Get job completion history over time."""
        history = []
        try:
            sql = """
                WITH RECURSIVE
                timepoints AS (
                    SELECT ? as t
                    UNION ALL
                    SELECT datetime(t, ?) 
                    FROM timepoints 
                    WHERE t < ?
                ),
                counts AS (
                    SELECT 
                        timepoints.t as timestamp,
                        jobs.state,
                        COUNT(*) as count
                    FROM timepoints
                    LEFT JOIN jobs ON (
                        jobs.completed_at IS NOT NULL
                        AND jobs.completed_at <= timepoints.t
                        AND jobs.completed_at > datetime(timepoints.t, ?)
                    )
                    GROUP BY timepoints.t, jobs.state
                )
                SELECT * FROM counts
                ORDER BY timestamp DESC
            """
            now = utc_now()
            start = now - window
            
            result = await (await self.store.client).execute(sql, [
                now.isoformat(),
                f"-{int(interval.total_seconds())} seconds",
                start.isoformat(),
                f"-{int(interval.total_seconds())} seconds"
            ])
            
            current_time = None
            current_counts = {}
            
            for row in result.rows:
                timestamp = datetime.fromisoformat(row[0])
                
                if current_time != timestamp:
                    if current_time:
                        history.append({
                            "timestamp": current_time.isoformat(),
                            "counts": current_counts.copy()
                        })
                    current_time = timestamp
                    current_counts = {s.value: 0 for s in JobState}
                    
                if row[1]:  # state column
                    current_counts[row[1]] = row[2]
                    
            if current_time:
                history.append({
                    "timestamp": current_time.isoformat(),
                    "counts": current_counts
                })
                
        except Exception as e:
            logger.error("error_getting_history", error=str(e))
            
        return history

async def jobs_handler(request: web.Request) -> web.Response:
    """Handle jobs endpoint requests."""
    try:
        store = request.app["store"]
        dashboard = Dashboard(store)
        stats = await dashboard.get_job_stats()
        return web.json_response({"status": "success", "data": stats})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def workers_handler(request: web.Request) -> web.Response:
    """Handle workers endpoint requests."""
    try:
        store = request.app["store"]
        dashboard = Dashboard(store)
        workers = await dashboard.get_active_workers()
        return web.json_response({"status": "success", "data": workers})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def history_handler(request: web.Request) -> web.Response:
    """Handle job history endpoint requests."""
    try:
        store = request.app["store"]
        dashboard = Dashboard(store)
        history = await dashboard.get_job_history()
        return web.json_response({"status": "success", "data": history})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def index_handler(request: web.Request) -> web.Response:
    """Handle root endpoint requests."""
    routes = {
        "jobs": "/api/jobs",
        "workers": "/api/workers", 
        "history": "/api/history"
    }
    return web.json_response({"status": "success", "endpoints": routes})

async def run_dashboard() -> None:
    """Run the dashboard web server."""
    try:
        app = web.Application()
        store = LibSQLStore()
        
        app["store"] = store
        
        # Add routes
        app.router.add_get("/", index_handler)
        app.router.add_get("/api/jobs", jobs_handler)
        app.router.add_get("/api/workers", workers_handler)
        app.router.add_get("/api/history", history_handler)
        
        # Add CORS support
        app.add_routes([web.options("/{tail:.*}", lambda r: web.Response())])
        
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response
            
        app.middlewares.append(cors_middleware)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(
            runner,
            settings.dashboard_host,
            settings.dashboard_port
        )
        
        logger.info(
            "starting_dashboard",
            host=settings.dashboard_host,
            port=settings.dashboard_port
        )
        
        await site.start()
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error("dashboard_error", error=str(e))
        raise
