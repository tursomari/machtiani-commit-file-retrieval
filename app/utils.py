import os
import logging
from enum import Enum
from typing import List, Dict
from lib.utils.enums import FilePathEntry

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define the base path
BASE_PATH = "/data/users/repositories/"

class DataDir(Enum):
    REPO = "repo"
    COMMITS_EMBEDDINGS = "commits/embeddings"
    COMMITS_LOGS = "commits/logs"
    CONTENT_EMBEDDINGS = "contents/embeddings"
    CONTENT_LOGS = "contents/logs"

    def get_path(self, project_name: str, dir_type: 'DataDir' = None) -> str:
        """
        Gets the full path for a specific project based on the directory type.
        If dir_type is provided, it returns the path for that specific directory type.

        :param project_name: The name of the project.
        :param dir_type: The specific directory type from the DataDir enum.
        :return: The full path to the requested directory.
        """
        if dir_type is None:
            dir_type = self
        return os.path.join(BASE_PATH, project_name, dir_type.value)

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

def retrieve_file_contents(project_name: str, file_paths: List[FilePathEntry]) -> Dict[str, str]:
    """
    Retrieves the content of files specified in the file_paths list within the given project.

    :param project_name: The name of the project.
    :param file_paths: A list of FilePathEntry objects.
    :return: A dictionary mapping file paths to their contents.
    """
    file_contents = {}
    repo_path = DataDir.REPO.get_path(project_name)
    skip_files = {"go.sum", "go.mod", "poetry.lock"}

    for entry in file_paths:
        if entry.path in skip_files:
            logger.debug(f"Skipping file: {entry.path}")
            continue

        full_path = os.path.join(repo_path, "git", entry.path)
        try:
            with open(full_path, 'r') as file:
                content = file.read()
                file_contents[entry.path] = content
                logger.debug(f"Retrieved content from file: {full_path}")
        except FileNotFoundError:
            logger.error(f"File not found: {full_path}")
        except IOError as e:
            logger.error(f"Error reading file {full_path}: {e}")

    return file_contents

# Example usage:
#if __name__ == "__main__":
#    file_paths = [
#        FilePathEntry(path="app/main.py"),
#        FilePathEntry(path="app/utils.py"),
#        FilePathEntry(path="README.md")
#    ]
#    contents = retrieve_file_contents("example_project", file_paths)
#    for path, content in contents.items():
#        logger.info(f"Content of {path}: {content[:100]}")  # Show only the first 100 characters

