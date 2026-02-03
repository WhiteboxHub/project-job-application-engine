from config.settings import settings
from core.logger import logger

class SafetyGuards:
    def __init__(self):
        self.applications_submitted = 0
        self.dry_run = settings.DRY_RUN

    def can_apply(self):
        """Checks if application limit has been reached."""
        # Limits disabled: always allow applying
        return True

    def increment_counter(self):
        if not self.dry_run:
            self.applications_submitted += 1
            logger.info(f"Counter: {self.applications_submitted}")
        else:
            logger.info(f"[DRY-RUN] Would increment counter. Current pseudo-count: {self.applications_submitted}")

    def is_dry_run(self):
        return self.dry_run

guards = SafetyGuards()
