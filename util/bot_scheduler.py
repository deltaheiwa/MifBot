import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class Scheduler:
    def __init__(self):
        self.scheduler: AsyncIOScheduler = None
        self.schedule()
        self.scheduler.start()
    
    def schedule(self):
        # Initialize scheduler
        schedule_log = logging.getLogger("apscheduler")
        schedule_log.setLevel(logging.WARNING)

        job_defaults = {
            "coalesce": True,
            "max_instances": 5,
            "misfire_grace_time": 15,
            "replace_existing": True,
        }

        self.scheduler = AsyncIOScheduler(job_defaults=job_defaults, logger=schedule_log)