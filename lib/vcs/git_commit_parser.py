import git
import json
import os
import logging
from app.utils import DataDir

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitCommitParser:
    def __init__(self, json_data, project):
        """
        Initialize with a JSON object in the same format as what `get_commits_up_to_depth_or_oid` returns.
        """
        if isinstance(json_data, list):
            self.commits = json_data
        else:
            logger.warning("Provided json_data is not a list; initializing with an empty list.")
            self.commits = []  # Ensure it's a list
        self.new_commits = []
        # Get the first OID from the initialized JSON and assign it to self.stop_oid
        if self.commits:
            self.stop_oid = self.commits[0]['oid']
        else:
            self.stop_oid = None
        self.project = project
        self.git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
        self.repo = git.Repo(self.git_project_path)  # Initialize the repo object

    def get_commit_info_at_depth(self, repo, depth):
        try:
            # Get the total number of commits in the repository
            total_commits = repo.git.rev_list('--count', 'HEAD')
            if depth >= int(total_commits):
                return None  # Depth exceeds the number of commits, return None

            # Get the commit object at the given depth
            commit = repo.commit(f'HEAD~{depth}')

            # Get the commit message
            message = commit.message.strip()

            # Get the list of files changed in the commit
            files = []
            for diff in commit.diff(commit.parents[0] if commit.parents else None):
                files.append(diff.a_path)

            # Only return commit info if there are file changes
            if files:  # Check if the files list is not empty
                return {
                    "oid": commit.hexsha,
                    "message": message,
                    "files": files
                }
            else:
                return None  # No file changes, skip this commit

        except Exception as e:
            logger.error(f"Error processing commit at depth {depth}: {e}")
            return None

    async def get_commits_up_to_depth_or_oid(self, repo_path, max_depth):
        try:
            repo = git.Repo(repo_path)
            commits = []
            for i in range(max_depth):
                commit_info = self.get_commit_info_at_depth(repo, i)
                if commit_info:
                    if commit_info['oid'] == self.stop_oid:
                        break  # Stop just before processing the specified OID
                    logger.info(f"Added OID {commit_info['oid']}")
                    commits.append(commit_info)
                else:
                    logger.info(f"No file changes for commit at depth {i}, skipping...")
                    break  # Stop if we've reached an invalid commit or error occurs

            return commits

        except Exception as e:
            logger.error(f"Error accessing the repository: {e}")
            return []

    async def add_commits_to_log(self, repo_path, max_depth):
        """
        Adds the result of `get_commits_up_to_depth_or_oid` to the beginning of the commits log JSON object.
        """
        new_commits = await self.get_commits_up_to_depth_or_oid(repo_path, max_depth)
        self.new_commits = new_commits
        self.commits = new_commits + self.commits  # Prepend the new commits to the existing log

    def is_file_deleted(self, file_path, commit_oid):
        """
        Check if a file was deleted in the history of the given commit.

        :param repo: The Git repository object.
        :param file_path: The file path to check.
        :param commit_oid: The OID of the commit to check against.
        :return: True if the file was deleted, False otherwise.
        """
        try:
            commit = self.repo.commit(commit_oid)
            # Check if the file exists in the commit
            if file_path in commit.stats['files']:
                return False  # File exists in this commit
            # Check parent commits to see if it was deleted
            for parent in commit.parents:
                if file_path in parent.stats['files']:
                    return False  # File exists in the parent commit
            return True  # File was deleted

        except Exception as e:
            logger.error(f"Error checking if file {file_path} was deleted: {e}")
            return False  # Default to False if there's an error

    def get_files_from_commits(self, oid):
        for commit in self.commits:
            if commit.get('oid') == oid:
                files = commit.get('files', [])
                existing_files = []
                for file in files:
                    if not self.is_file_deleted(file, oid):
                        existing_files.append(file)
                    else:
                        logger.info(f"File {file} was deleted. Skipping.")
                return existing_files
        return []
