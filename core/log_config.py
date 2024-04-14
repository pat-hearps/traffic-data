import logging
import sys
from pathlib import Path
from typing import Union

from decouple import config

from core.directory import DIR

LOG_FORMAT = "%(levelname)-5s | %(asctime)s | %(module)s:%(lineno)-3s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
VERBOSE = 5  # add chattier level option below DEBUG
logging.addLevelName(VERBOSE, "VERBOSE")
# LOG_LEVEL can be changed via env variable
LOG_LEVEL = config("LOG_LEVEL", default="INFO", cast=str).upper()


def get_logger(
    name: str, level: Union[str, int] = LOG_LEVEL, log_file: Path = DIR.DATA.LOGS / "logs.log"
) -> logging.Logger:
    """
    Sets up standardised logging formats and output. To be imported and used on a per-module basis.

    Usage:

    from core.log_config import get_logger
    log = get_logger(__name__)

    log.info(f"message here")

    :param name: preferably the inbuilt python dunder variable __name__
    :param level: logging module level, either string e.g. "DEBUG" or corresponding int e.g. 10
    :param log_file: file to write logs into
    :return: ready to use logger object with standardised formatting and outputs
    """
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger(name)

    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
