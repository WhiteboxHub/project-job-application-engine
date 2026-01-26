from config.settings import settings
from core.logger import logger

class SafetyGuards:
    def __init__(self):
        self.applications_submitted = 0
        self.max_apps = settings.MAX_APPLICATIONS_PER_RUN
        self.dry_run = settings.DRY_RUN

    def can_apply(self):
        """Checks if application limit has been reached."""
        if self.applications_submitted >= self.max_apps:
            logger.warning(f"Safety Stop: Reached max applications ({self.max_apps})")
            return False
        return True

    def increment_counter(self):
        if not self.dry_run:
            self.applications_submitted += 1
            logger.info(f"Counter: {self.applications_submitted}/{self.max_apps}")
        else:
             logger.info(f"[DRY-RUN] Would increment counter. Current pseudo-count: {self.applications_submitted}")

    def is_dry_run(self):
        return self.dry_run

guards = SafetyGuards()
