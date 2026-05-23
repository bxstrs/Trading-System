'''src/utils/logger.py'''
import os
import sys
from loguru import logger

# Add custom level
try:
    logger.level("SIGNAL", no=25, color="<green>")
except Exception:
    pass

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
valid_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL", "SIGNAL"]
if LOG_LEVEL not in valid_levels:
    LOG_LEVEL = "INFO"

# Configure loguru: terminal + file
logger.remove() # remove default handler
logger.add(sys.stdout, level=LOG_LEVEL, colorize=True)
os.makedirs("logs", exist_ok=True)
logger.add("logs/trading_{time:YYYY-MM-DD}.log", rotation="100 MB", retention="30 days", level=LOG_LEVEL)

def log(msg: str, level: str = "INFO", source: str | None = None) -> None:
    try:
        level = str(level).upper()
        if level not in valid_levels:
            level = "INFO"
            
        if source:
            msg = f"[{source}] {msg}"
            
        logger.opt(depth=1).log(level, msg)
    except Exception as e:
        # FINAL safety net
        print(f"[LOGGER FAILURE] {e} | original_msg={msg}", flush=True)