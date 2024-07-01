import logging
from rich.logging import RichHandler
import os

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
logging.basicConfig(
    level=LOGGING_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log", mode="w")],
)

console_handler = RichHandler(markup=True)
console_handler.setLevel(LOGGING_LEVEL)
# Set format for console output
console_handler.setFormatter(
    logging.Formatter(
        "%(message)s",
    )
)

logger = logging.getLogger("rich")
logger.addHandler(console_handler)


if __name__ == "__main__":
    logger.debug("This is an debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
