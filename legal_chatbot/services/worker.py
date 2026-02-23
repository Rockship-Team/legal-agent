"""Background worker — runs data pipeline on schedule using APScheduler."""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from legal_chatbot.models.pipeline import PipelineRun, WorkerJob, WorkerStatus
from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)


class PipelineWorker:
    """Background worker that runs data pipeline on schedule."""

    def __init__(self):
        self.settings = get_settings()
        self._scheduler = None
        self._pipeline = None
        self._db = None

    @property
    def scheduler(self):
        """Lazy-load APScheduler."""
        if self._scheduler is None:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
        return self._scheduler

    @property
    def pipeline(self):
        """Lazy-load pipeline service."""
        if self._pipeline is None:
            from legal_chatbot.db.supabase import get_database
            from legal_chatbot.services.pipeline import PipelineService
            db = get_database()
            self._pipeline = PipelineService(db)
        return self._pipeline

    @property
    def db(self):
        """Lazy-load database client."""
        if self._db is None:
            from legal_chatbot.db.supabase import get_database
            self._db = get_database()
        return self._db

    async def start(self) -> None:
        """Load active categories from DB, create cron jobs, start scheduler.

        Postconditions:
        - scheduler.running == True
        - One cron job per active category
        - Jobs staggered to avoid concurrent crawls
        """
        if self._scheduler and self._scheduler.running:
            logger.warning("Worker already running")
            return

        logger.info("Starting pipeline worker...")

        # Load categories with worker config
        categories = self.db.get_all_categories_with_stats()
        active_cats = [
            c for c in categories
            if c.get("worker_status") == "active" and c.get("is_active", True)
        ]

        if not active_cats:
            logger.warning("No active categories found for worker")
            return

        # Create cron jobs per category
        from apscheduler.triggers.cron import CronTrigger

        for cat in active_cats:
            schedule = cat.get("worker_schedule", self.settings.worker_default_schedule)
            time_str = cat.get("worker_time", self.settings.worker_default_time)

            try:
                hour, minute = time_str.split(":")
                hour, minute = int(hour), int(minute)
            except (ValueError, AttributeError):
                hour, minute = 2, 0

            # Build cron trigger based on schedule
            if schedule == "daily":
                trigger = CronTrigger(hour=hour, minute=minute)
            elif schedule == "weekly":
                trigger = CronTrigger(day_of_week="sun", hour=hour, minute=minute)
            elif schedule == "monthly":
                trigger = CronTrigger(day=1, hour=hour, minute=minute)
            else:
                trigger = CronTrigger(day_of_week="sun", hour=hour, minute=minute)

            job_id = f"pipeline_{cat['name']}"
            self.scheduler.add_job(
                self.run_category,
                trigger=trigger,
                args=[cat["name"]],
                id=job_id,
                name=f"Pipeline: {cat.get('display_name', cat['name'])}",
                replace_existing=True,
                max_instances=1,
            )
            logger.info(
                f"  Scheduled: {cat['name']} ({schedule} {time_str})"
            )

        self.scheduler.start()
        logger.info(f"Worker started with {len(active_cats)} scheduled jobs")

    def stop(self) -> None:
        """Gracefully shutdown scheduler, wait for running jobs.

        Postconditions:
        - scheduler.running == False
        - No orphaned async tasks
        """
        if self._scheduler and self._scheduler.running:
            logger.info("Stopping pipeline worker...")
            self._scheduler.shutdown(wait=True)
            logger.info("Worker stopped")
        else:
            logger.info("Worker not running")

    async def run_category(self, category_name: str) -> Optional[PipelineRun]:
        """Run pipeline for a single category with retry.

        Retry: 3 attempts, exponential backoff (30s, 60s, 120s).
        On all-fail: logs error, updates category last_worker_status='failed'.
        """
        max_retries = self.settings.worker_retry_count
        base_backoff = self.settings.worker_retry_backoff

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Running pipeline for {category_name} "
                    f"(attempt {attempt}/{max_retries})"
                )
                result = await self.pipeline.run(
                    category=category_name,
                    trigger_type="scheduled",
                )

                # Success — update category status
                category_id = self.pipeline.get_category_id(category_name)
                if category_id:
                    status = "success" if result.status.value == "completed" else "partial"
                    self.db.update_category_worker_status(category_id, status)

                logger.info(
                    f"Pipeline {category_name} completed: "
                    f"{result.documents_new} new, {result.documents_skipped} skipped"
                )
                return result

            except Exception as e:
                logger.error(
                    f"Pipeline {category_name} failed (attempt {attempt}): {e}"
                )
                if attempt < max_retries:
                    backoff = base_backoff * (2 ** (attempt - 1))
                    logger.info(f"  Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)

        # All retries exhausted
        logger.error(f"Pipeline {category_name} failed after {max_retries} attempts")
        category_id = self.pipeline.get_category_id(category_name)
        if category_id:
            self.db.update_category_worker_status(category_id, "failed")

        return None

    def get_status(self) -> WorkerStatus:
        """Return current worker state + job schedule."""
        is_running = bool(self._scheduler and self._scheduler.running)

        jobs = []
        if is_running:
            for job in self._scheduler.get_jobs():
                # Extract category from job args
                category = job.args[0] if job.args else "unknown"
                jobs.append(WorkerJob(
                    id=job.id,
                    name=job.name or job.id,
                    category=category,
                    next_run=job.next_run_time,
                    trigger=str(job.trigger),
                    status="active",
                ))

        return WorkerStatus(
            is_running=is_running,
            jobs=jobs,
            last_check=datetime.now(),
        )

    def get_schedule(self) -> List[WorkerJob]:
        """Return schedule for all categories."""
        status = self.get_status()
        return status.jobs


# Singleton
_worker: Optional[PipelineWorker] = None


def get_worker() -> PipelineWorker:
    """Get or create worker singleton."""
    global _worker
    if _worker is None:
        _worker = PipelineWorker()
    return _worker
