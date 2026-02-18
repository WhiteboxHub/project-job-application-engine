"""
Guards - Safety Mechanisms for Automation
Handles rate limiting, DRY_RUN mode, and application counters
"""

from config.settings import settings
from core.logger import logger

class Guards:
    """Safety mechanisms to prevent over-application and respect limits"""
    
    def __init__(self):
        self.application_count = 0
        
    def can_apply(self) -> bool:
        """Check if we can apply to another job"""
        max_apps = settings.MAX_APPLICATIONS_PER_RUN
        # Treat 999999 or higher as unlimited
        if max_apps >= 999999:
            return True
        
        if self.application_count >= max_apps:
            logger.warning(f"Reached maximum applications limit: {max_apps}")
            return False
        return True
    
    def increment_counter(self):
        """Increment application counter"""
        self.application_count += 1
        max_apps = settings.MAX_APPLICATIONS_PER_RUN
        max_display = "Unlimited" if max_apps >= 999999 else str(max_apps)
        logger.info(f"Applications submitted: {self.application_count}/{max_display}")
    
    def is_dry_run(self) -> bool:
        """Check if running in dry-run mode"""
        return settings.DRY_RUN
    
    def get_stats(self) -> dict:
        """Get current guard statistics"""
        max_apps = settings.MAX_APPLICATIONS_PER_RUN
        return {
            'applications_submitted': self.application_count,
            'max_applications': max_apps,
            'remaining': max_apps - self.application_count,
            'dry_run_mode': settings.DRY_RUN
        }

# Singleton instance
guards = Guards()
