import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.runner import EngineRunner
from core.logger import logger

def test_wipro():
    logger.info("Starting Wipro Dry-Run Test...")
    runner = EngineRunner()
    runner.run(site_filter="Wipro")

if __name__ == "__main__":
    test_wipro()
