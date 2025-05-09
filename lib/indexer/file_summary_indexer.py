import os
import time
import logging
import json
import asyncio
from pydantic import HttpUrl
from fastapi import HTTPException # Note: Consider if HTTPException is appropriate here or if custom exceptions are better
from lib.ai.embeddings_model import EmbeddingModel
from lib.vcs.git_content_manager import GitContentManager
from app.utils import DataDir
from lib.ai.llm_model import LlmModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from lib.utils.utilities import (
    validate_files_embeddings,
    # validate_commits_logs, # This import seems unused in FileSummaryGenerator
)
from lib.utils.log_utils import log_error, LoggedError, LogsStatus, reset_status

class FileSummaryGenerator:
    def __init__(
        self,
        project_name: str,
        commit_logs,
        llm_model_api_key: str,
        llm_model_base_url: HttpUrl,
        embeddings_model_api_key: str,
        git_project_path: str,
        llm_model: str,
        ignore_files: list = None,
        existing_files_embeddings=None,
        embeddings_model="all-MiniLM-L6-v2",
        use_mock_llm: bool = False,
        status_manager_hook=None,
        stage_key_hook=None,
        overall_progress_calculator_hook=None,
    ):
        self.logger = logging.getLogger(__name__)

        self.project_name = project_name
        self.logger.info(f"Initializing FileSummaryGenerator for project: {self.project_name}")
        self.commit_logs = commit_logs
        self.embeddings_model_name = embeddings_model
        self.summary_model = llm_model
        self.git_project_path = git_project_path
        self.ignore_files = ignore_files if ignore_files is not None else []

        self.llm_model_api_key = llm_model_api_key
        self.llm_model_base_url = str(llm_model_base_url)
        self.embeddings_model_api_key = embeddings_model_api_key
        self.use_mock_llm = use_mock_llm

        self.embedding_generator = EmbeddingModel(
            embeddings_model_api_key=self.embeddings_model_api_key,
            embedding_model_base_url=llm_model_base_url, # Ensure this is the correct base URL for embeddings model
            embeddings_model=self.embeddings_model_name,
            use_mock_llm=self.use_mock_llm
        )

        self.existing_file_embeddings = existing_files_embeddings if existing_files_embeddings is not None else {}
        self.logger.info(f"Loaded {len(self.existing_file_embeddings)} existing file embeddings.")

        self.files_embeddings_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project_name), "files_embeddings.json")

        if self.ignore_files:
            self.logger.info(f"Ignored files on initialization: {', '.join(self.ignore_files)}")
        else:
            self.logger.info("No files are set to be ignored on initialization.")

        self.status_manager_hook = status_manager_hook
        self.stage_key_hook = stage_key_hook
        self.overall_progress_calculator_hook = overall_progress_calculator_hook
        self.status_tracker = LogsStatus(self.project_name)
        self._processed_items = 0
        self._total_items = 0

    def _get_progress_percentage(self):
        """Calculate progress as a percentage based on summarization."""
        if self._total_items == 0:
            return 0
        return min(100, int((self._processed_items / self._total_items) * 100))

    def _get_file_content(self, file_path):
        """Retrieve the content of the file at the given path relative to git_project_path."""
        full_file_path = os.path.join(self.git_project_path, file_path)
        try:
            with open(full_file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            self.logger.warning(f"File not found: {full_file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading file {full_file_path}: {e}")
            return None

    def commit_file_summaries_embedding_file(self):
        """Commits the file_embeddings.json to the content repository."""
        embedding_file_path = self.files_embeddings_path # Use instance variable

        if not os.path.exists(embedding_file_path):
            self.logger.error(f"Embedding file does not exist at {embedding_file_path} for commit.")
            # This error should ideally be handled before calling this method or be more critical
            raise FileNotFoundError(f"Embedding file does not exist at {embedding_file_path}")

        git_content_manager = GitContentManager(self.project_name)
        try:
            git_content_manager.add_file(embedding_file_path)
            # Using a more specific commit message
            git_content_manager.commit_and_tag(f'Update file embeddings via FileSummaryGenerator')
            self.logger.info(f"Successfully added and committed the embedding file: {embedding_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to add and commit the embedding file {embedding_file_path}: {str(e)}")
            # Propagate as a runtime error rather than HTTP directly
            raise RuntimeError(f"Failed to commit the embedding file: {str(e)}")

    def _summarize_content_with_progress(self, contents_to_process: list[tuple[str, str]]):
        """
        Generates summaries for file contents using LLM via ThreadPoolExecutor
        and updates progress specific to summarization.
        """
        self.logger.info(f"Starting summarization for {len(contents_to_process)} files.")
        summaries = [None] * len(contents_to_process)
        max_workers = 10

        def summarize_single(file_path, content):
            if not content or not content.strip():
                self.logger.warning(f"No text content to summarize for file: {file_path}")
                return "eddf150cd15072ba4a8474209ec090fedd4d79e4" # Placeholder for skipped

            prompt = f"Summarize this file ({file_path}):\n{content}"
            llm_instance = LlmModel(
                api_key=self.llm_model_api_key,
                model=self.summary_model,
                base_url=self.llm_model_base_url,
                use_mock_llm=self.use_mock_llm
            )
            try:
                return llm_instance.send_prompt(prompt)
            except Exception as e:
                self.logger.error(f"Error generating summary for {file_path}: {e}")
                log_error(f"Error generating summary for {file_path}: {e}", self.project_name)
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(summarize_single, file_p, file_c): idx
                for idx, (file_p, file_c) in enumerate(contents_to_process)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                original_file_path = contents_to_process[index][0]
                try:
                    summary_result = future.result()
                    summaries[index] = summary_result
                except Exception as e:
                    # This catches exceptions from future.result() itself, not from summarize_single's try-except
                    self.logger.error(f"Future for summarizing {original_file_path} resulted in error: {e}")
                    log_error(f"Future error during summary for {original_file_path}: {e}", self.project_name)
                    summaries[index] = None
                finally:
                    # Increment processed items for summarization attempt regardless of success/failure
                    self._processed_items += 1
                    if not (self.status_manager_hook and self.stage_key_hook):
                        self.status_tracker.update_status(self._get_progress_percentage())

        valid_summaries_count = len([s for s in summaries if s and s != "eddf150cd15072ba4a8474209ec090fedd4d79e4"])
        self.logger.info(f"Summarization phase complete. Generated {valid_summaries_count} valid summaries out of {len(contents_to_process)} files.")
        return summaries

    def _filter_files_from_new_commits(self):
        """Filters files from commit logs, respecting the ignore list."""
        new_files_map = {} # Using a map to avoid duplicates from multiple commits
        for commit in self.commit_logs:
            commit_oid = commit.get('oid')
            if not commit_oid:
                self.logger.warning("Commit data missing 'oid', skipping.")
                continue

            for file_path_in_commit in commit.get('files', []):
                if file_path_in_commit in self.ignore_files:
                    self.logger.debug(f"File '{file_path_in_commit}' from commit {commit_oid} is in ignore list.")
                    continue
                new_files_map[file_path_in_commit] = commit_oid # Keeps latest commit_oid if file in multiple commits

        self.logger.info(f"Identified {len(new_files_map)} unique files from new commits for potential processing.")
        return new_files_map

    async def generate(self):
        """
        Generates file summaries and embeddings. Progress tracking covers ONLY the summarization phase.
        """
        start_time = time.time()

        # Filter new files and prepare contents
        new_files_dict = self._filter_files_from_new_commits()

        if not new_files_dict:
            self.logger.info("No new files from commits to process.")
            self.status_tracker.update_status(100)
            return self.existing_file_embeddings

        contents_to_process = []
        for file_path in new_files_dict.keys():
            if file_path in self.ignore_files:
                continue
            content = self._get_file_content(file_path)
            if content:
                contents_to_process.append((file_path, content))
            else:
                self.logger.info(f"File '{file_path}' is empty or unreadable, will not be summarized.")

        # Select status updater: hooked or fallback
        status_updater_local = self.status_manager_hook if (self.status_manager_hook and self.stage_key_hook) else self.status_tracker
        current_stage_key_local = self.stage_key_hook if (self.status_manager_hook and self.stage_key_hook) else self.project_name

        # Initialize progress counters
        self._total_items = len(contents_to_process)
        self._processed_items = 0

        # Handle no content case
        if not contents_to_process:
            self.logger.info("No file contents to process after filtering (all files empty, unreadable, or ignored).")
            if status_updater_local and self.stage_key_hook:
                overall_val = None
                if self.overall_progress_calculator_hook:
                    status = await status_updater_local.read_status_async()
                    overall_val = self.overall_progress_calculator_hook(status)
                await status_updater_local.update_stage_progress(
                    current_stage_key_local,
                    100,
                    overall_progress_val=overall_val
                )
            else:
                self.status_tracker.update_status(100)
            return self.existing_file_embeddings

        # Start summarization progress
        if status_updater_local and self.stage_key_hook:
            overall_val = None
            if self.overall_progress_calculator_hook:
                status = await status_updater_local.read_status_async()
                overall_val = self.overall_progress_calculator_hook(status)
            await status_updater_local.update_stage_progress(
                current_stage_key_local,
                0,
                overall_progress_val=overall_val
            )
            await status_updater_local.start_periodic_updates(
                current_stage_key_local,
                self._get_progress_percentage,
                interval=1.0,
                overall_calculator=self.overall_progress_calculator_hook
            )
        else:
            self.status_tracker.update_status(0)
            await self.status_tracker.start_periodic_updates(
                self.project_name,
                self._get_progress_percentage,
                interval=1.0
            )

        loop = asyncio.get_running_loop()
        summaries = []
        success_flag = True
        try:
            summaries = await loop.run_in_executor(
                None,
                self._summarize_content_with_progress,
                contents_to_process
            )
        except Exception as e:
            success_flag = False
            self.logger.error(f"Error during summarization stage: {e}", exc_info=True)
            log_error(f"Summarization error: {e}", self.project_name)
            if status_updater_local and self.stage_key_hook:
                overall_val = None
                if self.overall_progress_calculator_hook:
                    status = await status_updater_local.read_status_async()
                    overall_val = self.overall_progress_calculator_hook(status)
                await status_updater_local.mark_stage_status(
                    current_stage_key_local,
                    "failed",
                    str(e),
                    overall_progress_val=overall_val
                )
            raise
        finally:
            if status_updater_local and self.stage_key_hook:
                await status_updater_local.stop_periodic_updates(
                    current_stage_key_local,
                    success=success_flag,
                    overall_calculator=self.overall_progress_calculator_hook
                )
            else:
                await self.status_tracker.stop_periodic_updates(
                    self.project_name,
                    success=success_flag
                )

        self.logger.info("Summarization progress tracking finished (100%). Proceeding with embeddings.")

        # Stage 2: Embedding (Not tracked for progress percentage)
        valid_files_for_embedding = []
        summaries_to_embed_text = []

        for i, summary_text in enumerate(summaries):
            if summary_text and summary_text != "eddf150cd15072ba4a8474209ec090fedd4d79e4":
                original_file_path = contents_to_process[i][0]
                valid_files_for_embedding.append((original_file_path, summary_text))
                summaries_to_embed_text.append(summary_text)
            else:
                self.logger.info(f"Skipping embedding for {contents_to_process[i][0]} due to missing/invalid summary.")

        if not summaries_to_embed_text:
            self.logger.info("No valid summaries available to generate embeddings.")
        else:
            self.logger.info(f"Generating embeddings for {len(summaries_to_embed_text)} valid summaries.")
            embeddings = await loop.run_in_executor(
                None,
                self.embedding_generator.embed_list_of_text,
                summaries_to_embed_text
            )

            for i, embedding_vector in enumerate(embeddings):
                file_path, summary_text = valid_files_for_embedding[i]

                self.existing_file_embeddings[file_path] = {
                    "summary": summary_text,
                    "embedding": embedding_vector
                }
                self.logger.debug(f"Stored summary and embedding for file: '{file_path}'")

            validate_files_embeddings(self.existing_file_embeddings)

            def _save_embeddings_sync():
                with open(self.files_embeddings_path, 'w', encoding='utf-8') as f:
                    json.dump(self.existing_file_embeddings, f, indent=4)
                self.logger.info(f"Saved updated embeddings to {self.files_embeddings_path}")

            await loop.run_in_executor(None, _save_embeddings_sync)

            if self.use_mock_llm:
                await loop.run_in_executor(None, self.commit_file_summaries_embedding_file)

        duration = time.time() - start_time
        self.logger.info(f"FileSummaryGenerator.generate completed. Total duration: {duration:.2f} seconds.")
        return self.existing_file_embeddings
