
import os
import logging
from git import Repo, GitCommandError
from pydantic import SecretStr
from app.utils import DataDir
from lib.utils.utilities import add_safe_directory

# Configure logging
logger = logging.getLogger(__name__)

class GitContentManager:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.content_path = DataDir.CONTENT.get_path(project_name)
        self.content_git_path = os.path.join(self.content_path, ".git")
        self.repo = self._initialize_repo()


    def _initialize_repo(self):
        if not os.path.exists(self.content_path):
            os.makedirs(self.content_path)

        if not os.path.exists(self.content_git_path):
            repo = Repo.init(self.content_path)
            logger.info(f"Initialized a new Git repository at {self.content_path}")
            add_safe_directory(self.content_path)
            repo.git.config('user.email', '')  # Set user email to an empty string
            repo.git.config('user.name', 'machtiani')  # Set user name to "machtiani"
        else:
            repo = Repo(self.content_path)
            add_safe_directory(self.content_path)

        return repo

    def add_file(self, file_path: str):
        """Add a file to the Git repository."""
        try:
            add_safe_directory(self.content_path)
            self.repo.git.add(file_path)
            logger.info(f"Added file {file_path} to the repository.")
        except Exception as e:
            logger.error(f"Failed to add file {file_path}: {str(e)}")
            raise

    def commit(self, message: str):
        """Commit changes to the repository."""
        try:
            add_safe_directory(self.content_path)
            self.repo.git.config('user.email', '')  # Set user email to an empty string
            self.repo.git.config('user.name', 'machtiani')  # Set user name to "machtiani"
            self.repo.git.commit('-m', message)
            logger.info(f"Committed changes with message: '{message}'")
        except Exception as e:
            logger.error(f"Failed to commit changes: {str(e)}")
            raise

    def remove_all_remotes(self):
        """Remove all remotes from the repository."""
        try:
            remote_names = [remote.name for remote in self.repo.remotes]
            for remote_name in remote_names:
                self.repo.delete_remote(remote_name)
            logger.info("All remotes have been successfully removed.")
        except Exception as e:
            logger.error(f"An error occurred while removing remotes: {str(e)}")
            raise

    def check_repo(self):
        """Check the repository and return its status."""
        try:
            logger.info(f"Checking repository at {self.content_path}")
            return {
                "current_branch": self.repo.active_branch.name,
                "commit_count": len(list(self.repo.iter_commits())),
            }
        except Exception as e:
            logger.error(f"Failed to check repository: {str(e)}")
            raise
