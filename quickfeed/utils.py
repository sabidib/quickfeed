import json
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class AnsiColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ColorfulFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: AnsiColors.BLUE,
        logging.INFO: AnsiColors.GREEN,
        logging.WARNING: AnsiColors.WARNING,
        logging.ERROR: AnsiColors.FAIL,
        logging.CRITICAL: AnsiColors.FAIL + AnsiColors.BOLD,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, AnsiColors.END)
        record.msg = color + record.msg + AnsiColors.END
        return super().format(record)


def setup_database(sqlalchemy_database_url: str):
    engine = create_engine(sqlalchemy_database_url)
    local_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return local_session_maker


def get_config(path: str) -> dict:
    with open(path, 'r', encoding="utf-8") as file:
        config = json.load(file)
    return config


def configure_logging(config: dict): # pylint: disable=unused-argument
    logger = logging.getLogger("quickfeed")
    logger.setLevel(level=logging.DEBUG)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Set the log level for the handler

    # Define a formatter with a timestamp
    formatter = ColorfulFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)
