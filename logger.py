import logging
import sys
from typing import Any

class LoggerSetup:
    def __init__(self, log_file: str, log_level: str):
        self.log_file = log_file
        self.log_level = log_level
        self.logger = self.setup_logging()

    def setup_logging(self) -> logging.Logger:
        logger = logging.getLogger('PipelineLogger')
        logger.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

        # File Handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Stream Handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        # Prevent duplicate logs
        logger.propagate = False

        return logger
