import os
import logging
from enum import Enum

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

    def get_path(self, project_name: str) -> str:
        """
        Gets the full path for a specific project based on the directory type.

        :param project_name: The name of the project.
        :return: The full path to the requested directory.
        """
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

# Example usage:
#if __name__ == "__main__":
#    project_name = "example_project"
#
#    # Create all directories for the project
#    DataDir.create_all(project_name)
#
#    # Get specific directory path
#    repo_dir = DataDir.REPO.get_path(project_name)
#    commits_embeddings_dir = DataDir.COMMITS_EMBEDDINGS.get_path(project_name)
#
#    logger.debug(f"Repo Directory: {repo_dir}")
#    logger.debug(f"Commits Embeddings Directory: {commits_embeddings_dir}")

