"""
Logging and monitoring utilities.
Handles all logging operations with timestamps.
"""

import sys
from datetime import datetime


class Logger:
    """Logger class for proxy server operations."""

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
        print(log_message)
        sys.stdout.flush()

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
