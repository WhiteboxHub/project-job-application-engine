import sys
import os
import subprocess

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import logger
from engine.runner import EngineRunner

def main():
    """Entry point for the Wellfound Job Application Engine"""
    logger.info("=" * 60)
    logger.info("🚀 Wellfound Job Application Engine")
    logger.info("=" * 60)
    
    print("\nAvailable Actions:")
    print("1. Run Wellfound Engine (Discover Jobs)")
    print("2. Initialize Database")
    print("q. Quit")
    
    choice = input("\nSelect an option: ").strip().lower()
    
    if choice == '1':
        runner = EngineRunner()
        runner.run(site_filter="Wellfound")
    elif choice == '2':
        subprocess.run([sys.executable, "scripts/init_db.py"])
    elif choice == 'q':
        sys.exit(0)
    else:
        logger.error("Invalid selection")

if __name__ == "__main__":
    main()
