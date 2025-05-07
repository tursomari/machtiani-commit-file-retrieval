import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def reset_logs(project_name: str) -> None:
    """
    Reset (create or clear) the logs.txt file for a specific project.
    This should be called before generating messages for commits.

    Args:
        project_name (str): The name of the project
    """
    from app.utils import DataDir

    logs_path = os.path.join(DataDir.STORE.get_path(project_name), "logs.txt")

    try:
        # Create an empty file (overwrites if exists)
        with open(logs_path, 'w') as file:
            pass
        logger.info(f"Reset logs for project {project_name}")
    except Exception as e:
        logger.error(f"Error resetting logs for project {project_name}: {e}")

def log_error(error_message: str, project_name: str) -> None:
    """
    Write an error message to the logs.txt file for a specific project.
    This should be called if there are any errors during generating messages for commits.

    Args:
        error_message (str): The error message to write
        project_name (str): The name of the project
    """
    from app.utils import DataDir

    logs_path = os.path.join(DataDir.STORE.get_path(project_name), "logs.txt")

    try:
        with open(logs_path, 'w') as file:
            file.write(f"ERROR: {error_message}")
        logger.info(f"Logged error for project {project_name}: {error_message}")
    except Exception as e:
        logger.error(f"Error logging error for project {project_name}: {e}")

def read_logs(project_name: str) -> Optional[str]:
    """
    Read the contents of the logs.txt file for a specific project.

    Args:
        project_name (str): The name of the project

    Returns:
        Optional[str]: The contents of the logs file, or None if the file doesn't exist or is empty
    """
    from app.utils import DataDir

    logs_path = os.path.join(DataDir.STORE.get_path(project_name), "logs.txt")

    if not os.path.exists(logs_path):
        return None

    try:
        with open(logs_path, 'r') as file:
            content = file.read()
            # Return None if the file is empty (no errors)
        return content if content.strip() else None
    except Exception as e:
        logger.error(f"Error reading logs for project {project_name}: {e}")
        return None