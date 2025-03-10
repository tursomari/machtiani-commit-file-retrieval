import git
import json
import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from lib.utils.enums import FilePathEntry
from lib.vcs.git_content_manager import GitContentManager
from lib.indexer.file_summary_indexer import FileSummaryGenerator
from app.utils import (
    DataDir,
    count_tokens,
    retrieve_file_contents,
    send_prompt_to_openai,
    send_prompt_to_openai_async,
)

from lib.utils.utilities import (
    read_json_file,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitCommitManager:
    def __init__(
        self,
        json_data,
        project,
        api_key: str,
        commit_message_model="gpt-4o-mini",
        ignore_files: List[str] = [],
        files_summaries_json: Dict[str, str] = {},
        skip_summaries: bool = False
    ):

        self.is_first_run = True
        self.openai_api_key = api_key
        self.commit_message_model = commit_message_model
        self.summary_cache = files_summaries_json
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
            self.is_first_run = False
        else:
            self.stop_oid = None

        logger.info(f"is first run: {self.is_first_run}")
        self.project = project
        self.git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
        self.repo = git.Repo(self.git_project_path)  # Initialize the repo object
        self.ignore_files = ignore_files
        self.skip_summaries = skip_summaries

    def get_commit_info_at_depth(self, repo, depth):
        try:
            total_commits = int(repo.git.rev_list('--count', 'HEAD'))
            if depth >= total_commits:
                return None

            commit = repo.commit(f'HEAD~{depth}')
            logger.info(f"Processing commit {commit.hexsha} at depth {depth}")

            message = commit.message.strip()
            files = []
            messages = [message]
            diffs_info = {}

            if commit.parents:
                # Inverts the commits so additions are subtractions, and vice versa
                #diffs = commit.diff(commit.parents[0], create_patch=True)

                diffs = commit.parents[0].diff(commit, create_patch=True)
            else:
                NULL_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
                diffs = commit.diff(NULL_TREE, create_patch=True)


            for diff in diffs:
                # Use the non-None path, whether it's a_path or b_path
                file_path = diff.a_path if diff.a_path is not None else diff.b_path
                files.append(file_path)
                diffs_info[file_path] = {
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
                    "message": messages,
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

            # Start with the first commit and compare OIDs
            if self.commits and self.stop_oid != self.commits[0]['oid']:
                logger.info(f"Looking for stop_oid {self.stop_oid} in the existing commit list.")
                # Iterate through existing commits to find a match
                for n, commit in enumerate(self.commits):
                    if commit['oid'] == self.stop_oid:
                        logger.info(f"Found stop_oid {self.stop_oid} at index {n}.")
                        return self.commits[:n + 1]  # Return commits up to the found stop_oid
                logger.warning(f"stop_oid {self.stop_oid} not found in the existing commits.")

            # If no matching stop_oid is found in the existing commits, proceed as usual
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

    async def add_commits_and_summaries_to_log(self, repo_path, max_depth):
        # Retrieve new commits from the repository
        all_new_commits = self.get_commits_up_to_depth_or_oid(repo_path, max_depth)
        # Filter out commits that already exist in the current commit log
        existing_oids = {commit['oid'] for commit in self.commits}
        self.new_commits = [commit for commit in all_new_commits if commit['oid'] not in existing_oids]

        if self.is_first_run and not self.skip_summaries:
            files_summaries_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(self.project), "files_embeddings.json")
            existing_files_summaries_json = await asyncio.to_thread(read_json_file, files_summaries_file_path)

            file_summary_generator = FileSummaryGenerator(
                project_name=self.project,
                commit_logs=self.new_commits,
                api_key=self.openai_api_key,
                git_project_path=self.git_project_path,
                ignore_files=self.ignore_files,
                existing_file_embeddings=existing_files_summaries_json
            )

            self.summary_cache = await asyncio.to_thread(file_summary_generator.generate)
            logger.info(f"generated file summaries")

        async def process_commit(commit):
            if self.skip_summaries:
                commit['summaries'] = []
            else:
                files = commit.get('files', [])
                # Run all file summarizations concurrently for this commit
                commit['summaries'] = await asyncio.gather(
                    *(self.summarize_file(file) for file in files)
                )

        # Process each new commit concurrently
        await asyncio.gather(*(process_commit(commit) for commit in self.new_commits))

        # Prepend the new commits to the existing log
        logger.info(f"Existing commits in logs: {self.commits}")
        self.commits = self.new_commits + self.commits

        logger.info(f"Added new commits: {self.new_commits}")

    async def summarize_file(self, file_path: str):
        logger.info(f"Summary cache {self.summary_cache}")
        # Use caching only if it's the first run
        logger.info(f"summarize file path {file_path}")
        if self.is_first_run:
            if file_path in self.summary_cache:
               logger.info(f"Using cached summary for {file_path}")
               return self.summary_cache[file_path]['summary']

        contents_dict = retrieve_file_contents(self.project, [FilePathEntry(path=file_path)], self.ignore_files)
        if file_path not in contents_dict or not contents_dict[file_path].strip():
            logger.warning(f"No text content to summarize for file: {file_path}")
            return "eddf150cd15072ba4a8474209ec090fedd4d79e4"

        content = contents_dict[file_path]
        prompt = f"Summarize this {file_path}:\n{content}"
        try:
            summary = await send_prompt_to_openai_async(prompt, self.openai_api_key, self.commit_message_model)
            return summary
        except Exception as e:
            logger.error(f"Error generating summary for {file_path}: {e}")
            return f"Error generating summary: {e}"

    async def amplify_commits(self, base_prompt, temperature, per_file=False):
        sem = asyncio.Semaphore(10)  # Adjust based on API limits

        async def generate_message(commit_index, prompt):
            async with sem:
                try:
                    message = await send_prompt_to_openai_async(
                        prompt, self.openai_api_key, self.commit_message_model, temperature
                    )
                    self.new_commits[commit_index]['message'].append(message)
                except Exception as e:
                    logger.error(f"Error generating commit message for commit {commit_index}: {e}")

        tasks = []
        for commit_index, commit in enumerate(self.new_commits):
            diffs = commit.get('diffs', {})
            if per_file and len(diffs) > 1:
                for file_name, diff_info in diffs.items():
                    diff_text = diff_info.get('diff', '')
                    diff_block = f"{file_name}\n{diff_text}"
                    prompt = base_prompt + diff_block
                    tasks.append(generate_message(commit_index, prompt))
            elif not per_file:
                if diffs:
                    diff_blocks = [
                        f"{file_name}\n{diff_info.get('diff', '')}"
                        for file_name, diff_info in diffs.items()
                    ]
                    combined_diffs = "\n\n".join(diff_blocks)
                    prompt = base_prompt + combined_diffs
                else:
                    prompt = base_prompt
                tasks.append(generate_message(commit_index, prompt))

        if tasks:
            await asyncio.gather(*tasks)
        logger.info(f"Amplified new commits: {self.new_commits}")

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

