import time
import git
import json
import os
import logging
import asyncio
from pydantic import HttpUrl
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from lib.utils.enums import FilePathEntry
from lib.vcs.git_content_manager import GitContentManager
from lib.indexer.file_summary_indexer import FileSummaryGenerator
from lib.ai.llm_model import LlmModel
from app.utils import (
    DataDir,
    count_tokens,
    retrieve_file_contents,
)

from lib.utils.utilities import (
    read_json_file,
    validate_files_embeddings,
    validate_commits_logs,
)

logger = logging.getLogger(__name__)

class GitCommitManager:
    def __init__(
        self,
        commits_logs,
        project_name,
        llm_model_api_key: str,
        llm_model_base_url: HttpUrl,
        embeddings_model_api_key: str,
        head: str,
        llm_model="gpt-4o-mini",
        embeddings_model="text-embedding-3-large",
        ignore_files: List[str] = [],
        files_embeddings: Dict[str, str] = {},
        skip_summaries: bool = False,
        use_mock_llm: bool = False,
    ):
        start_time = time.time()
        if files_embeddings:
            validate_files_embeddings(files_embeddings)
        if commits_logs:  # This is always checked since it's initialized in __init__
            validate_commits_logs(commits_logs)

        self.is_first_run = True
        self.embeddings_model_api_key = embeddings_model_api_key
        self.llm_model_api_key = llm_model_api_key
        self.llm_model_base_url = str(llm_model_base_url)
        self.llm_model = llm_model
        self.embeddings_model = embeddings_model
        self.summary_cache = files_embeddings
        self.use_mock_llm = use_mock_llm
        """
        Initialize with a JSON object in the same format as what `get_commits_up_to_depth_or_oid` returns.
        """
        if isinstance(commits_logs, list):
            self.commits_logs = commits_logs
        else:
            logger.warning("Provided json_data is not a list; initializing with an empty list.")
            self.commits_logs = []  # Ensure it's a list
        self.new_commits = []
        # Get the first OID from the initialized JSON and assign it to self.stop_oid
        if self.commits_logs:
            self.stop_oid = self.commits_logs[0]['oid']
            self.is_first_run = False
        else:
            self.stop_oid = None

        logger.info(f"is first run: {self.is_first_run}")
        self.project_name = project_name
        self.git_project_path = os.path.join(DataDir.REPO.get_path(project_name), "git")
        self.repo = git.Repo(self.git_project_path)  # Initialize the repo object

        logger.info(f"GitCommitManager: Checking out to commit: {head}")
        self.repo.git.checkout(head)

        self.ignore_files = ignore_files
        self.skip_summaries = skip_summaries
        elapsed_time = time.time() - start_time
        logger.critical(f"Initialization completed in {elapsed_time:.2f} seconds")

        self.semaphore = asyncio.Semaphore(20)  # Control concurrent LLM requests
        self.file_read_semaphore = asyncio.Semaphore(100)  # Control file I/O concurrency

    def get_commit_info(self, commit):
        start_time = time.time()
        try:
            logger.info(f"Processing commit {commit.hexsha}")

            message = commit.message.strip()
            files = []
            messages = [message]
            diffs_info = {}

            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, create_patch=True)
            else:
                NULL_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
                diffs = commit.diff(NULL_TREE, create_patch=True)

            for diff in diffs:
                file_path = diff.a_path if diff.a_path is not None else diff.b_path
                files.append(file_path)
                diffs_info[file_path] = {
                    'diff': diff.diff.decode('utf-8') if diff.diff else '',
                    'changes': {
                        'added': diff.change_type == 'A',
                        'deleted': diff.change_type == 'D',
                    }
                }
            logger.info(f"Files changed in commit {commit.hexsha}: {files}")

            if files:
                elapsed_time = time.time() - start_time
                logger.info(f"get_commit_info completed in {elapsed_time:.2f} seconds")
                return {
                    "oid": commit.hexsha,
                    "message": messages,
                    "files": files,
                    "diffs": diffs_info
                }
            else:
                logger.info(f"No file changes for commit {commit.hexsha}, skipping...")
                return None

        except Exception as e:
            logger.error(f"Error processing commit {commit.hexsha}: {e}")
            return None

    def get_commits_up_to_depth_or_oid(self, repo_path, max_depth):
        start_time = time.time()
        try:
            repo = git.Repo(repo_path)
            commits = []

            # Precompute commits list once
            commits_list = list(repo.iter_commits('HEAD', max_count=max_depth))
            total_commits = len(commits_list)

            # Existing stop_oid check logic remains the same
            if self.commits_logs and self.stop_oid != self.commits_logs[0]['oid']:
                logger.info(f"Looking for stop_oid {self.stop_oid} in existing commits")
                for n, existing_commit in enumerate(self.commits_logs):

                    if existing_commit['oid'] is not None and existing_commit['oid'] == self.stop_oid:
                        logger.info(f"Found stop_oid at index {n}")
                        return self.commits_logs[:n+1]

            # Process precomputed commits
            for commit in commits_list:
                commit_info = self.get_commit_info(commit)
                if not commit_info:
                    logger.warning(f"Skipping commit {commit.hexsha} due to condition in get_commit_info (e.g., no file changes)")
                    continue # Skip to the next commit instead of stopping
                if commit_info['oid'] is not None and commit_info['oid'] == self.stop_oid:
                    break
                commits.append(commit_info)
                if len(commits) >= max_depth:
                    break

            elapsed_time = time.time() - start_time
            logger.critical(f"Processed {len(commits)} commits in {elapsed_time:.2f} seconds")
            return commits

        except Exception as e:
            logger.error(f"Error accessing repository: {e}")
            return []

    async def add_commits_and_summaries_to_log(self, repo_path, max_depth):
        start_time = time.time()
        logger.critical("Starting add_commits_and_summaries_to_log")

        # Retrieve and filter commits
        all_new_commits = await asyncio.to_thread(self.get_commits_up_to_depth_or_oid, repo_path, max_depth)
        existing_oids = {commit['oid'] for commit in self.commits_logs}
        self.new_commits = [commit for commit in all_new_commits if commit['oid'] not in existing_oids]

        # Handle first-run summaries if needed
        if not self.skip_summaries and self.is_first_run:
            files_summaries_file_path = os.path.join(
                DataDir.CONTENT_EMBEDDINGS.get_path(self.project_name),
                "files_embeddings.json"
            )
            existing_files_summaries_json = await asyncio.to_thread(read_json_file, files_summaries_file_path)

            if existing_files_summaries_json:
                validate_files_embeddings(existing_files_summaries_json)

            self.summary_cache = await asyncio.to_thread(
                FileSummaryGenerator(
                    project_name=self.project_name,
                    commit_logs=self.new_commits,
                    llm_model_api_key=self.llm_model_api_key,
                    llm_model_base_url=self.llm_model_base_url,
                    embeddings_model_api_key=self.embeddings_model_api_key,
                    git_project_path=self.git_project_path,
                    ignore_files=self.ignore_files,
                    existing_files_embeddings=existing_files_summaries_json,
                    use_mock_llm=self.use_mock_llm,
                ).generate
            )

        # Process all files across all commits with maximum concurrency
        if not self.skip_summaries:
            await self._process_all_files_concurrently()

        # Update commit logs
        self.commits_logs = self.new_commits + self.commits_logs
        elapsed_time = time.time() - start_time
        logger.critical(f"Completed in {elapsed_time:.2f} seconds")

    async def _process_all_files_concurrently(self):
        """Process all files across all commits with optimized concurrency"""
        tasks = []

        for commit in self.new_commits:
            if not commit.get('files'):
                commit['summaries'] = []
                continue

            # Pre-allocate summary list
            commit['summaries'] = [None] * len(commit['files'])

            # Create tasks for each file
            for idx, file_path in enumerate(commit['files']):
                tasks.append(self._process_single_file(commit, idx, file_path))

        # Run all file processing tasks with controlled concurrency
        await asyncio.gather(*tasks)

    async def _process_single_file(self, commit, file_index, file_path):
        """Process a single file and store result in the commit's summaries list"""
        try:
            summary = await self.summarize_file(file_path)
            commit['summaries'][file_index] = summary
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            commit['summaries'][file_index] = f"Error: {e}"

    async def summarize_file(self, file_path: str):
        """Optimized file summarization with caching and concurrency control"""
        # Check cache first
        if self.is_first_run and file_path in self.summary_cache:
            return self.summary_cache[file_path]['summary']

        # Async file read with concurrency control
        async with self.file_read_semaphore:
            contents_dict = await asyncio.to_thread(
                retrieve_file_contents,
                self.project_name,
                [FilePathEntry(path=file_path)],
                self.ignore_files
            )

        if not contents_dict.get(file_path, "").strip():
            return "eddf150cd15072ba4a8474209ec090fedd4d79e4"

        # Process with LLM with concurrency control
        async with self.semaphore:
            llm = LlmModel(
                api_key=self.llm_model_api_key,
                model=self.llm_model,
                base_url=self.llm_model_base_url,
                use_mock_llm=self.use_mock_llm,
                max_tokens=500
            )
            prompt = f"Summarize this {file_path}:\n{contents_dict[file_path]}"
            return await llm.send_prompt_async(prompt)

    async def amplify_commits(self, base_prompt, temperature, per_file=False):
        start_time = time.time()
        sem = asyncio.Semaphore(10)  # Adjust based on API limits

        async def generate_message(commit_index, prompt):
            async with sem:
                logger.info(f"Calling generate_message with use_mock_llm: {self.use_mock_llm}")
                llm_instance = LlmModel(api_key=self.llm_model_api_key, model=self.llm_model, temperature=temperature, base_url=self.llm_model_base_url, use_mock_llm=self.use_mock_llm, max_tokens=200)
                try:
                    message = await llm_instance.send_prompt_async(prompt)
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
        elapsed_time = time.time() - start_time
        logger.critical(f"amplify_commits completed in {elapsed_time:.2f} seconds")

    def is_file_deleted(self, file_path):
        start_time = time.time()
        """
        Check if a file exists in the current worktree.

        :param file_path: The file path to check.
        :return: True if the file does not exist in the worktree, False otherwise.
        """
        try:
            # Get the correct worktree path (parent of .git directory)
            full_path = os.path.join(self.git_project_path, file_path)

            # Check if the file exists in the worktree
            file_exists = os.path.exists(full_path)

            elapsed_time = time.time() - start_time
            return not file_exists

        except Exception as e:
            logger.error(f"Error checking file {file_path}: {e}")
            return False  # Default to False if there's an error

    #def is_file_deleted(self, file_path, commit_oid):
    #    start_time = time.time()
    #    """
    #    Check if a file was deleted in the history of the given commit.

    #    :param repo: The Git repository object.
    #    :param file_path: The file path to check.
    #    :param commit_oid: The OID of the commit to check against.
    #    :return: True if the file was deleted, False otherwise.
    #    """
    #    try:
    #        commit = self.repo.commit(commit_oid)

    #        # Check if the file exists in the commit
    #        if file_path in commit.tree:
    #            return False  # File exists in this commit

    #        # Check parent commits to see if it was deleted
    #        for parent in commit.parents:
    #            if file_path in parent.tree:
    #                return False  # File exists in the parent commit

    #        elapsed_time = time.time() - start_time
    #        logger.critical(f"is_file_deleted completed in {elapsed_time:.2f} seconds")
    #        return True  # File was deleted

    #    except Exception as e:
    #        logger.error(f"Error checking if file {file_path} was deleted: {e}")
    #        return False  # Default to False if there's an error

    def get_files_from_commits(self, oid):
        start_time = time.time()
        for commit in self.commits_logs:
            if commit.get('oid') == oid:
                files = commit.get('files', [])
                existing_files = []
                for file in files:
                    if not self.is_file_deleted(file):
                        existing_files.append(file)
                    else:
                        logger.debug(f"File {file} was deleted. Skipping.")
                elapsed_time = time.time() - start_time
                logger.critical(f"get_files_from_commits completed in {elapsed_time:.2f} seconds")
                return existing_files
        return []

    def count_tokens_in_files(self, new_commits, project_name: str, ignore_files: List[str]):
        start_time = time.time()
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

        elapsed_time = time.time() - start_time
        logger.critical(f"count_tokens_in_files completed in {elapsed_time:.2f} seconds")
        return token_counts
