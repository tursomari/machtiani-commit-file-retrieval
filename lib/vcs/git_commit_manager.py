import git
import json
import os
import logging
import asyncio
from typing import List
from lib.utils.enums import FilePathEntry
from app.utils import (
    DataDir,
    count_tokens,
    retrieve_file_contents,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitCommitManager:
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
            total_commits = int(repo.git.rev_list('--count', 'HEAD'))
            if depth >= total_commits:
                return None

            commit = repo.commit(f'HEAD~{depth}')
            logger.info(f"Processing commit {commit.hexsha} at depth {depth}")

            message = commit.message.strip()
            files = []
            diffs_info = {}

            if commit.parents:
                diffs = commit.diff(commit.parents[0], create_patch=True)
            else:
                NULL_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
                diffs = commit.diff(NULL_TREE, create_patch=True)


            for diff in diffs:
                files.append(diff.a_path)
                diffs_info[diff.a_path] = {
                    'diff': diff.diff.decode('utf-8') if diff.diff else '',
                    'changes': {
                        'added': diff.change_type == 'A',  # If the file is added
                        'deleted': diff.change_type == 'D',  # If the file is deleted
                    }
                }

            logger.info(f"Files changed in commit {commit.hexsha}: {files}")

            if files:
                return {
                    "oid": commit.hexsha,
                    "message": message,
                    "files": files,
                    "diffs": diffs_info  # Include diffs in the returned info
                }
            else:
                logger.info(f"No file changes for commit {commit.hexsha}, skipping...")
                return None

        except Exception as e:
            logger.error(f"Error processing commit at depth {depth}: {e}")
            return None

    def get_commits_up_to_depth_or_oid(self, repo_path, max_depth):
        try:
            repo = git.Repo(repo_path)
            commits = []
            for i in range(max_depth):
                commit_info = self.get_commit_info_at_depth(repo, i)
                if commit_info:
                    if commit_info['oid'] == self.stop_oid:
                        break
                    logger.info(f"Added OID {commit_info['oid']}")
                    commits.append(commit_info)
                else:
                    logger.info(f"No file changes for commit at depth {i}, skipping...")
                    break
            return commits
        except Exception as e:
            logger.error(f"Error accessing the repository: {e}")
            return []

    async def add_commits_to_log(self, repo_path, max_depth):
        new_commits = self.get_commits_up_to_depth_or_oid(repo_path, max_depth)
        self.new_commits = new_commits
        self.commits = new_commits + self.commits  # Prepend the new commits to the existing log
        # Log the added new commits
        logger.info(f"Added new commits: {self.new_commits}")

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

    def count_tokens_in_files(self, new_commits, project_name: str, ignore_files: List[str]):
        """
        Count tokens in all files changed in new commits.
        :param new_commits: List of new commits.
        :param project_name: The name of the project.
        :return: A dictionary with file paths and their corresponding token counts.
        """
        token_counts = {}
        repo_path = DataDir.REPO.get_path(project_name)

        for commit in new_commits:
            files = commit.get('files', [])
            existing_files = []

            for file_path in files:
                full_path = os.path.join(repo_path, "git", file_path)
                if os.path.isfile(full_path):
                    existing_files.append(FilePathEntry(path=file_path))
                else:
                    logger.error(f"File does not exist: {full_path}")

            # Retrieve the contents of existing files
            file_contents = retrieve_file_contents(project_name, existing_files, ignore_files)

            # Count tokens for each file content
            for file_path, content in file_contents.items():
                tokens = count_tokens(content)
                token_counts[file_path] = tokens
                logger.info(f"Counted {tokens} tokens in file: {file_path}")

        return token_counts
