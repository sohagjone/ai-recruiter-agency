import logging
import os
from datetime import datetime


def setup_logger():
    """Setup application logging (safe to call on every Streamlit rerun)"""
    logger = logging.getLogger("AI_Recruiter")

    # Already configured on a previous rerun, so just reuse it
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler (this is what shows up in Streamlit Cloud "Manage app" logs)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # File handler (optional, don't crash the app if the folder can't be created)
    try:
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir, f"recruitment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning(f"File logging disabled: {e}")

    return logger
