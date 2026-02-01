import logging
import sys
import os

# If running directly, add project root to path
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

logger = logging.getLogger(__name__)

def validate_secrets():
    """
    Validates that essential secrets and configurations are present.
    Raises ValueError if critical settings are missing.
    """
    missing = []
    
    if not settings.DB_PASSWORD:
        missing.append("DB_PASSWORD")
        
    # Check if we are in production-like mode (not just testing)
    # For now, just basic checks
        
    if missing:
        msg = f"Missing critical environment variables: {', '.join(missing)}"
        logger.critical(msg)
        raise ValueError(msg)
    
    logger.info("Secrets validation passed.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        validate_secrets()
    except ValueError as e:
        sys.exit(1)
