# monitoring_service.py
import asyncio
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List
from minerva.core.services.tender_notification_service import notify_tender_updates
from minerva.tasks.sources.tender_monitor_manager import TenderMonitoringManager

logger = logging.getLogger("minerva.tasks.monitoring_tasks")

monitoring_manager = TenderMonitoringManager()

async def get_updates_for_tenders(date: Optional[str] = None, worker_index: int = 0, total_workers: int = 1) -> Dict[str, Any]:
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    logger.info(f"Starting monitoring for date={date}")
    active_monitoring_sources = monitoring_manager.get_active_monitoring_sources()
    semaphore = asyncio.Semaphore(5)

    # Split monitoring sources among workers
    assigned_sources = [
        source for idx, source in enumerate(active_monitoring_sources)
        if idx % total_workers == worker_index
    ]
    if not assigned_sources:
        logger.info(f"No monitoring sources assigned to worker {worker_index}")
        return {"status": "ok", "updates": []}

    async def process_monitoring(monitoring_source):
        async with semaphore:
            service = monitoring_manager.create_monitoring_service(monitoring_source)
            return await service.process_tenders_monitoring(date)

    tasks = [process_monitoring(source) for source in assigned_sources]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    updates_results = [
        {source.value: result if not isinstance(result, Exception) else str(result)}
        for source, result in zip(assigned_sources, results)
    ]

    # Collect all successful updates for coordination-level notifications
    all_updates: List[Dict] = []
    for source, result in zip(assigned_sources, results):
        if not isinstance(result, Exception) and isinstance(result, list):
            all_updates.extend(result)
    
    # Send coordination-level notifications if we have updates and this is the primary worker
    if all_updates and worker_index == 0:
        try:
            coordination_notification_results = await notify_tender_updates(all_updates)
            logger.info(f"Coordination-level notification results: {coordination_notification_results}")
        except Exception as e:
            logger.error(f"Failed to send coordination-level notifications: {str(e)}")

    logger.info("Monitoring completed.")
    return {
        "status": "ok",
        "updates": updates_results
    }
