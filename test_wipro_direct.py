import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.runner import EngineRunner
from core.logger import logger
from core.candidate_loader import CandidateLoader
from config.settings import settings

settings.DRY_RUN = True
logger.info("Directly testing Wipro...")

runner = EngineRunner()
# Load candidate data from guest json if available
candidate_data = CandidateLoader.load()
runner.run(site_filter="Wipro", candidate_data=candidate_data)
