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
        self.repo_path = os.path.join(DataDir.REPO.get_path(self.project_name), "git")
        self.repo_git_path = os.path.join(self.repo_path, ".git")
        self.content_repo, self.repo = self._initialize_repo()

    def _initialize_repo(self):
        if not os.path.exists(self.content_path):
            os.makedirs(self.content_path)

        if not os.path.exists(self.content_git_path):
            content_repo = Repo.init(self.content_path)
            logger.info(f"Initialized a new Git content repository at {self.content_path}")
            add_safe_directory(self.content_path)
            content_repo.git.config('user.email', '')  # Set user email to an empty string
            content_repo.git.config('user.name', 'machtiani')  # Set user name to "machtiani"
        else:
            content_repo = Repo(self.content_path)
            add_safe_directory(self.content_path)

        if os.path.exists(self.repo_git_path):
            repo = Repo(self.repo_path)
            add_safe_directory(self.repo_path)
            return content_repo, repo
        else:
            logger.error(f"There is no Git repository at {self.repo_path}")
            raise Exception(f"There is no Git repository at {self.repo_path}")

    def add_file(self, file_path: str):
        """Add a file to the Git repository."""
        try:
            add_safe_directory(self.content_path)
            self.content_repo.git.add(file_path)
            logger.info(f"Added file {file_path} to the repository.")
        except Exception as e:
            logger.error(f"Failed to add file {file_path}: {str(e)}")
            raise

    def commit_and_tag(self, message: str):
        """Commit changes to the repository and create a tag."""
        try:
            add_safe_directory(self.content_path)
            self.content_repo.git.config('user.email', '')  # Set user email to an empty string
            self.content_repo.git.config('user.name', 'machtiani')  # Set user name to "machtiani"

            # Check if there are changes to commit
            if not self.content_repo.git.status('--porcelain'):
                logger.info("Work tree is clean. No changes to commit.")
                # Directly create a tag since there are no changes
                self.create_tag()
            else:
                # Commit changes if there are any
                self.content_repo.git.commit('-m', message)
                logger.info(f"Committed changes with message: '{message}'")

                # Call create_tag after a successful commit
                self.create_tag()

        except Exception as e:
            logger.error(f"Failed to commit or create tag: {str(e)}")
            raise


    def remove_all_remotes(self):
        """Remove all remotes from the repository."""
        try:
            remote_names = [remote.name for remote in self.content_repo.remotes]
            for remote_name in remote_names:
                self.content_repo.delete_remote(remote_name)
            logger.info("All remotes have been successfully removed.")
        except Exception as e:
            logger.error(f"An error occurred while removing remotes: {str(e)}")
            raise

    def check_repo(self, repo):
        """Check the repository and return its status."""
        try:
            logger.info(f"Checking repository at {self.content_path}")
            return {
                "current_branch": repo.active_branch.name,
                "commit_count": len(list(repo.iter_commits())),
            }
        except Exception as e:
            logger.error(f"Failed to check repository: {str(e)}")
            raise

    def get_latest_commit_oid(self, repo) -> str:
        """Get the latest commit OID from the repository."""
        try:
            latest_commit = repo.head.commit
            logger.info(f"Latest commit OID: {latest_commit.hexsha}")
            return latest_commit.hexsha
        except Exception as e:
            logger.error(f"Failed to get latest commit OID: {str(e)}")
            raise

    def create_tag(self):
        """Create a tag in the content repository using the latest commit OID from the specified repository as the tag name."""
        try:
            add_safe_directory(self.content_path)
            # Get the latest commit OIDs
            repo_latest_commit_oid = self.get_latest_commit_oid(self.repo)
            content_repo_latest_commit_oid = self.get_latest_commit_oid(self.content_repo)

            # Attempt to create the lightweight tag without checking for duplicates
            self.content_repo.create_tag(repo_latest_commit_oid, ref=content_repo_latest_commit_oid)
            logger.info(f"Created tag '{repo_latest_commit_oid}' pointing to commit {content_repo_latest_commit_oid} in the content repository.")
        except Exception as e:
            logger.error(f"Failed to create tag '{repo_latest_commit_oid}': {str(e)}")
            raise

