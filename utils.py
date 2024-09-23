import os
from typing import Any
import logging

def create_directory(directory_path: str):
    try:
        os.makedirs(directory_path, exist_ok=True)
    except Exception as e:
        logging.getLogger('PipelineLogger').error(f"Failed to create directory {directory_path}: {e}")
        raise
