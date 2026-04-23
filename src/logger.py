"""
Logging and monitoring utilities.
Handles all logging operations with timestamps.
"""

import os
import sys
import threading
from datetime import datetime


class Logger:
    """Logger class for proxy server operations."""

    _log_file_path = None
    _lock = threading.Lock()

    @staticmethod
    def configure(log_file_path: str = "") -> None:
        """Configure optional persistent file logging path."""
        if not log_file_path:
            Logger._log_file_path = None
            return

        directory = os.path.dirname(log_file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        Logger._log_file_path = log_file_path

    @staticmethod
    def log(message: str, level: str = "INFO") -> None:
        """
        Log a message with timestamp.
        
        Args:
            message: The message to log
            level: Log level (INFO, ERROR, WARNING, DEBUG)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_message = f"[{timestamp}] [{level}] {message}"
        with Logger._lock:
            print(log_message)
            sys.stdout.flush()

            if Logger._log_file_path:
                try:
                    with open(Logger._log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write(log_message + "\n")
                except Exception as exc:
                    print(f"[LOGGER ERROR] Failed writing log file: {exc}", file=sys.stderr)

    @staticmethod
    def info(message: str) -> None:
        """Log info level message."""
        Logger.log(message, "INFO")

    @staticmethod
    def error(message: str) -> None:
        """Log error level message."""
        Logger.log(message, "ERROR")

    @staticmethod
    def warning(message: str) -> None:
        """Log warning level message."""
        Logger.log(message, "WARNING")

    @staticmethod
    def debug(message: str) -> None:
        """Log debug level message."""
        Logger.log(message, "DEBUG")
