"""Load supported data files for the MP1 pipeline."""

import json
import logging
from pathlib import Path

import pandas as pd
import yaml


logger = logging.getLogger(__name__)


def load_csv(filepath):
    """Load a CSV file into a pandas DataFrame."""
    data = pd.read_csv(filepath)
    logger.info("Loaded CSV file: %s (%d rows)", filepath, len(data))
    return data


def load_json(filepath):
    """Load a JSON file into a Python object."""
    with filepath.open("r", encoding="utf-8") as file:
        data = json.load(file)

    logger.info("Loaded JSON file: %s", filepath)
    return data


def load_yaml(filepath):
    """Load a YAML file into a Python object."""
    with filepath.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    logger.info("Loaded YAML file: %s", filepath)
    return data


def load_data(filepath):
    """Load a file using the loader selected by its extension."""
    path = Path(filepath)
    extension = path.suffix.lower()

    if extension == ".csv":
        return load_csv(path)
    if extension == ".json":
        return load_json(path)
    if extension == ".yaml":
        return load_yaml(path)

    logger.error("Unsupported file format: %s", extension)
    raise ValueError(f"Unsupported file format: {extension}")
