import os
import logging
import magic
from enum import Enum
from typing import List, Dict
from lib.utils.enums import FilePathEntry

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define the base path
BASE_PATH = "/data/users/repositories/"

class DataDir(Enum):
    STORE = "store"
    REPO = "repo"
    COMMITS_EMBEDDINGS = "commits/embeddings"
    COMMITS_LOGS = "commits/logs"
    CONTENT_EMBEDDINGS = "contents/embeddings"
    CONTENT_LOGS = "contents/logs"

    def get_path(self, project_name: str, dir_type: 'DataDir' = None) -> str:
        """
        Gets the full path for a specific project based on the current directory type.

        If the directory type is STORE, it returns only the base path joined with the project name.
        For other directory types, it appends the specific directory value to the project path.

        :param project_name: The name of the project.
        :return: The full path to the requested directory.
        """
        if self == DataDir.STORE:
            return os.path.join(BASE_PATH, project_name)
        return os.path.join(BASE_PATH, project_name, self.value)

    @staticmethod
    def create_all(project_name: str):
        """
        Creates all necessary directories for a project based on the project name.

        :param project_name: The name of the project.
        :return: None
        """
        for dir_type in DataDir:
            path = dir_type.get_path(project_name)
            os.makedirs(path, exist_ok=True)
            logger.debug(f"Created directory: {path}")

        logger.debug(f"All directories created for project '{project_name}'.")

    @staticmethod
    def list_projects() -> list:
        """
        Lists the names of all projects in the BASE_PATH directory.

        :return: A list of project names.
        """
        try:
            projects = [
                name for name in os.listdir(BASE_PATH)
                if os.path.isdir(os.path.join(BASE_PATH, name))
            ]
            logger.debug(f"Found projects: {projects}")
            return projects
        except FileNotFoundError:
            logger.error(f"Base path '{BASE_PATH}' not found.")
            return []

def is_text_file(filepath: str) -> bool:
    """Check if the file at the given path is a text file."""
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(filepath)

    # Check if the mime type starts with 'text/'
    return mime_type.startswith('text/')

def retrieve_file_contents(project_name: str, file_paths: List[FilePathEntry], ignore_files: List[str]) -> Dict[str, str]:
    file_contents = {}
    repo_path = DataDir.REPO.get_path(project_name)

    for entry in file_paths:
        full_path = os.path.join(repo_path, "git", entry.path)

        logger.debug(f"Checking file: {full_path}")

        # Skip files that are in the ignore list
        if entry.path in ignore_files:
            logger.warning(f"Skipping ignored file: {full_path}")
            continue  # Skip ignored files

        # Check if the file exists before any further processing
        if not os.path.isfile(full_path):
            logger.error(f"File not found: {full_path}")
            continue  # Skip if the file does not exist

        # Check if the file is a text file
        try:
            if not is_text_file(full_path):
                logger.warning(f"Skipping non-text file: {full_path}")
                continue  # Skip non-text files
        except Exception as e:
            logger.error(f"Error determining file type for {full_path}: {e}")
            continue  # Skip files that cause errors in type checking

        try:
            with open(full_path, 'r', encoding='utf-8') as file:  # Specify utf-8 encoding
                content = file.read()
                file_contents[entry.path] = content
                logger.debug(f"Retrieved content from file: {full_path}")
        except UnicodeDecodeError as e:
            logger.warning(f"Skipping file due to codec error: {full_path} - {e}")
            continue  # Skip files that raise codec errors
        except IOError as e:
            logger.error(f"Error reading file {full_path}: {e}")
            continue  # Continue to the next file on IOError

    return file_contents

def count_tokens(text: str) -> int:
    # Simple estimation: 1 token is approximately 4 characters (including spaces)
    return len(text) // 4 + 1
