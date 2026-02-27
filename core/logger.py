import logging
import sys
import json
from datetime import datetime

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logger(name="job_engine", level=logging.INFO, json_format=False):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        # Use errors='replace' to prevent crashes on non-UTF-8 terminals
        handler = logging.StreamHandler(sys.stdout)
        if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
            # Note: logging.StreamHandler doesn't take encoding/errors in older Python versions
            # but we can wrap the stream or just rely on the fact that we'll remove emojis anyway.
            # However, for robustness:
            handler.stream = open(sys.stdout.fileno(), mode='w', encoding=sys.stdout.encoding, 
                                 errors='replace', buffering=1)
        
        if json_format:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        
    return logger

# Default logger instance
logger = setup_logger()
