import asyncio
import logging
from datetime import datetime, timedelta

from minerva.config import logging_config
from minerva.core.models.user import User
from minerva.config.constants import UserRole
from minerva.api.routes.extensions.tenders.tender_analysis_routes import (
    cleanup_files_by_date,
    CleanupDateRange,
)

logging_config.setup_logging()
logger = logging.getLogger("minerva.tasks.cleanup_tasks")


async def run_cleanup_task(target_date: str) -> dict:
    """Run cleanup for public tenders filtered on *target_date*.

    The cleanup removes:
      * binary blobs stored in S3 / Vercel
      * vector representations from Pinecone
      * auxiliary Elasticsearch documents
      * the now-orphaned filtered tender documents themselves

    Parameters
    ----------
    target_date : str
        Date in the format YYYY-MM-DD.  All tenders whose *filter_timestamp*
        falls within this 24-hour period will be processed.
    Returns
    -------
    dict
        Summary produced by *cleanup_files_by_date*.
    """
    start_dt = datetime.fromisoformat(target_date)
    end_dt = start_dt + timedelta(days=1) - timedelta(microseconds=1)
    date_range = CleanupDateRange(start_date=start_dt, end_date=end_dt)

    # We just need a user object so the Pydantic validation passes and the
    # function can log who initiated the cleanup.  Grant it the ADMIN role so
    # authorisation checks – if ever added – do not fail.
    system_user = User(
        email="system-cleanup@minerva.ai",
        name="System Cleanup",
        role=UserRole.ADMIN,
    )

    logger.info(
        "Launching automated cleanup for date %s (initiated by system user)",
        target_date,
    )

    # Delegate the heavy lifting to the already-tested FastAPI route logic.
    result = await cleanup_files_by_date(date_range=date_range, current_user=system_user)  # type: ignore

    logger.info("Cleanup finished for %s – stats: %s", target_date, result)
    return result


async def main(
    worker_index: int,
    total_workers: int,
    target_date: str | None = None,
    logger: logging.Logger | None = None,
):
    """Entry-point used by *tasks_app.py*.

    Currently we run a single-worker setup, therefore *worker_index* and
    *total_workers* are accepted for signature parity but are otherwise
    unused.
    """
    if logger is None:
        logger = logging.getLogger("minerva.tasks.cleanup_tasks")
        logging_config.setup_logging()

    if target_date is None:
        target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    result = await run_cleanup_task(target_date=target_date)
    logger.info("Cleanup task completed – summary: %s", result)


if __name__ == "__main__":
    import sys

    worker_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    total_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    # Default target date: seven days ago
    date_arg = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(main(worker_index, total_workers, date_arg)) 