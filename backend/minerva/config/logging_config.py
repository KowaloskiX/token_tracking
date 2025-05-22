# logging_config.py

import os
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    # Determine the project root directory (minerva/) - two levels up from this file
    root_dir = os.path.dirname(os.path.dirname(__file__))  # Navigate from minerva/config/ to minerva/
    logs_dir = os.path.join(root_dir, "logs")
    
    # Create the logs directory if it doesn't exist
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except OSError as e:
        print(f"Failed to create log directory {logs_dir}: {e}", file=sys.stderr)
        # Fall back to a logs directory in the project root (retry with a relative path)
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs_fallback")
        os.makedirs(logs_dir, exist_ok=True)
    
    # Reset root logger handlers to avoid duplicates
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # Set up logging format
    formatter = logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] [%(process)d] %(message)s')
    
    # Console handler for stdout logging
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
    root_logger.addHandler(console)
    
    app_log_path = os.path.join(logs_dir, "minerva_app.log")
    app_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)
    root_logger.addHandler(app_handler)

    # Error-specific log file (WARNING and ERROR)
    error_log_path = os.path.join(logs_dir, "minerva_errors.log")
    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)  # Capture WARNING and ERROR
    root_logger.addHandler(error_handler)

    task_types = ["scraping_tasks", "analysis_tasks", "monitoring_tasks"]
    for task_type in task_types:
        log_path = os.path.join(logs_dir, f"{task_type}.log")
        task_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        task_handler.setFormatter(formatter)
        task_handler.setLevel(logging.INFO)
        
        task_logger = logging.getLogger(f"minerva.tasks.{task_type}")
        task_logger.setLevel(logging.INFO)
        # Remove existing handlers if any
        for handler in task_logger.handlers[:]:
            task_logger.removeHandler(handler)
        task_logger.addHandler(task_handler)
    
    # Celery beat log
    beat_log_path = os.path.join(logs_dir, "celery_beat.log")
    beat_handler = RotatingFileHandler(
        beat_log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    beat_handler.setFormatter(formatter)
    beat_handler.setLevel(logging.INFO)
    
    beat_logger = logging.getLogger("celery.beat")
    beat_logger.setLevel(logging.INFO)
    for handler in beat_logger.handlers[:]:
        beat_logger.removeHandler(handler)
    beat_handler.setLevel(logging.INFO)
    beat_logger.addHandler(beat_handler)
    
    # Set root logger level
    root_logger.setLevel(logging.INFO)
