
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.custom.dice import DiceStrategy
from core.logger import logger

def test_instantiation():
    print("Testing DiceStrategy instantiation...")
    try:
        # Mock objects
        driver = None
        job_site = None
        selectors = {}
        
        strategy = DiceStrategy(driver, job_site, selectors)
        print("Successfully instantiated DiceStrategy!")
        print(f"Applicant: {strategy.applicant_data.get('applicant', {}).get('first_name')}")
    except Exception as e:
        print(f"Failed to instantiate DiceStrategy: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_instantiation()
