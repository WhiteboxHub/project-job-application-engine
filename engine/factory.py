import importlib
from core.logger import logger

class StrategyFactory:
    @staticmethod
    def get_strategy(class_path: str, driver, job_site, selectors, candidate_profile=None):
        """
        Dynamically imports and instantiates a strategy class.
        e.g. strategies.custom.InsightGlobalStrategy
        """
        try:
            module_name, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            strategy_class = getattr(module, class_name)
            
            return strategy_class(driver, job_site, selectors, candidate_profile)
        except (ImportError, AttributeError) as e:
            logger.critical(f"Failed to load strategy '{class_path}': {e}")
            raise ValueError(f"Could not load strategy {class_path}")

strategy_factory = StrategyFactory()
