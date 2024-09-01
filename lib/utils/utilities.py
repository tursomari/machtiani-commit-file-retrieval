import json
import logging

logger = logging.getLogger(__name__)

def read_json_file(file_path):
    """
    Reads a JSON file and returns its content as a Python object.
    If the file doesn't exist or an error occurs, it returns an empty list.
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            logger.info(f"Successfully read data from {file_path}")
            return data
    except FileNotFoundError:
        logger.warning(f"File {file_path} not found. Returning an empty list.")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return []

def write_json_file(data, file_path):
    """
    Writes a Python object to a JSON file.
    If the file doesn't exist, it creates it.
    """
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=2)
            logger.info(f"Successfully wrote data to {file_path}")
    except IOError as e:
        logger.error(f"Error writing to file {file_path}: {e}")

