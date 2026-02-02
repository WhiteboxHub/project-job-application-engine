import time
from engine.factory import strategy_factory
from core.browser import browser_service
from core.logger import logger
from engine.guards import guards

class EngineRunner:
    def __init__(self):
        self.browser = None

    def run(self):
        """
        Main execution workflow.
        1. Initialize Browser
        2. Run Insight Global strategy directly (no database)
        3. Strategy handles discovery and application
        """
        logger.info("Starting Job Engine Runner...")
        
        try:
            # 1. Start Browser
            self.browser = browser_service.start_browser()
            
            # 2. Run Insight Global strategy directly
            # Import the strategy class directly
            from strategies.custom.insight_global import InsightGlobalStrategy
            
            # Create strategy instance
            strategy = InsightGlobalStrategy(self.browser, None, {})
            
            # Run the strategy
            applied_count = strategy.run_search_and_apply()
            logger.info(f"Strategy completed. Applied to {applied_count} jobs.")
                    
        except Exception as e:
            logger.critical(f"Engine crashed: {e}")
        finally:
            if self.browser:
                logger.info("Stopping browser...")
                browser_service.stop_browser()
        
