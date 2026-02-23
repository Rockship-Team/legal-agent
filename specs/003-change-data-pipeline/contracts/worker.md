# Contract: Worker Service

**Module**: `legal_chatbot/services/worker.py`

## Interface

```python
class PipelineWorker:
    """Background worker that runs data pipeline on schedule."""

    def __init__(self, config: Settings):
        """Initialize worker with APScheduler AsyncIOScheduler."""

    async def start(self) -> None:
        """Load active categories from DB, create cron jobs, start scheduler.

        Postconditions:
        - scheduler.running == True
        - One cron job per active category
        - Jobs staggered to avoid concurrent crawls
        """

    def stop(self) -> None:
        """Gracefully shutdown scheduler, wait for running jobs.

        Postconditions:
        - scheduler.running == False
        - No orphaned async tasks
        """

    async def run_category(self, category_name: str) -> PipelineResult:
        """Run pipeline for a single category with retry.

        Args:
            category_name: e.g. 'dat_dai', 'nha_o'

        Returns:
            PipelineResult with documents_new, documents_updated, etc.

        Retry:
            3 attempts, exponential backoff (30s, 60s, 120s)
            On all-fail: logs error, updates category last_worker_status='failed'
        """

    def get_status(self) -> WorkerStatus:
        """Return current worker state + job schedule.

        Returns:
            WorkerStatus with is_running, jobs list (id, name, next_run, trigger)
        """

    def get_schedule(self) -> List[WorkerJob]:
        """Return schedule for all categories.

        Returns:
            List of WorkerJob with category, schedule, time, status
        """
```

## Dependencies

- `APScheduler>=3.10.0` (AsyncIOScheduler, CronTrigger)
- `services/pipeline.py` (PipelineService)
- `db/supabase.py` (load categories, update stats)
- `utils/config.py` (Settings)

## Events

| Event | Trigger | Action |
|-------|---------|--------|
| Job start | Cron trigger fires | Log, set `last_worker_run_at` |
| Job success | Pipeline completes | Update `document_count`, `article_count`, set `last_worker_status='success'` |
| Job failure | All retries exhausted | Set `last_worker_status='failed'`, log error |
| Shutdown | SIGINT/SIGTERM | `scheduler.shutdown(wait=True)` |
