import os
import asyncio
import logging
import fnmatch  # Import fnmatch
from typing import List, Tuple  # Import Tuple
from pydantic import ValidationError, HttpUrl
from app.utils import retrieve_file_contents
from app.models.responses import FileSearchResponse, FileContentResponse
from lib.utils.utilities import url_to_folder_name, read_json_file
from lib.utils.enums import FilePathEntry
from lib.vcs.git_commit_manager import GitCommitManager
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.search.file_localization import FileLocalizer
from app.utils import DataDir

logger = logging.getLogger(__name__)

async def retrieve_file_contents_service(
    project_name: str,
    file_paths: List[FilePathEntry],
    ignore_files: List[str]
) -> FileContentResponse:
    """Service method to retrieve file contents."""
    retrieved_file_paths = []
    contents = {}

    try:
        logger.critical("Starting file content retrieval for project '%s'...", project_name)
        file_contents = await asyncio.to_thread(retrieve_file_contents, project_name, file_paths, ignore_files)
        logger.critical("Completed file content retrieval for project '%s'", project_name)

        if not file_contents:
            logger.warning("No file contents retrieved for project '%s' with provided file paths: %s", project_name, file_paths)

        for path in file_contents.keys():
            retrieved_file_paths.append(path)

    except ValidationError as e:
        logger.critical("Validation error retrieving files for project '%s': %s", project_name, e)
        raise ValueError(f"Validation error: {e}")
    except Exception as e:
        logger.critical("Critical error retrieving files for project '%s': %s", project_name, e)
        raise RuntimeError(f"Error retrieving file contents: {e}")

    return FileContentResponse(contents=file_contents, retrieved_file_paths=retrieved_file_paths)

# Helper function for filtering
def _filter_and_log_ignored_files(
    file_paths: List[FilePathEntry],
    ignore_patterns: List[str],
    source_description: str  # e.g., "commit <oid>" or "localization"
) -> Tuple[List[FilePathEntry], List[FilePathEntry]]:
    """
    Filters a list of FilePathEntry objects based on ignore patterns and logs ignored files.
    Returns a tuple: (kept_files, ignored_files_logged).
    """
    if not ignore_patterns:
        return file_paths, []  # No filtering needed

    kept_files = []
    ignored_files_logged = []
    for entry in file_paths:
        file_path = entry.path
        is_ignored = False
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                is_ignored = True
                break  # Matched an ignore pattern

        if is_ignored:
            ignored_files_logged.append(entry)
        else:
            kept_files.append(entry)

    if ignored_files_logged:
        ignored_paths = [entry.path for entry in ignored_files_logged]
        logger.info(
            f"{source_description}: Filtered out {len(ignored_paths)} ignored files "
            f"matching patterns in {ignore_patterns}. Ignored: {ignored_paths}"
        )

    return kept_files, ignored_files_logged

async def infer_file_service(
    prompt: str,
    project: str,
    mode: str,
    model: str,
    match_strength: str,
    llm_model_api_key: str,
    llm_model_base_url: HttpUrl,
    embeddings_model_api_key: str,
    ignore_files: List[str],
    head: str
) -> List[FileSearchResponse]:
    """Service method to infer file matches."""

    logger.info(f"llm key: {llm_model_api_key}")
    logger.info(f"llm base_url: {str(llm_model_base_url)}")

    project = url_to_folder_name(project)

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(
        commits_embedding_filepath=commits_embeddings_file_path,
        embeddings_model_api_key=embeddings_model_api_key,
        embedding_model_base_url=llm_model_base_url
    )

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    logger.info(f"infer_file_service calls GitCommitManager with head: {head}")  # Use f-string
    parser = GitCommitManager(
        commits_logs_json,
        project,
        llm_model_api_key=llm_model_api_key,
        llm_model_base_url=llm_model_base_url,
        embeddings_model_api_key=embeddings_model_api_key,
        head=head,
        llm_model=model,
        ignore_files=ignore_files,  # Pass ignore_files here if needed by parser logic
        skip_summaries=True,
    )

    logger.debug("Searching for commits closely matching prompt: '%s'...", prompt)
    closest_commit_matches = await matcher.find_closest_commits(prompt, match_strength, top_n=5)
    logger.debug("Found %d commit(s) matching prompt '%s'", len(closest_commit_matches), prompt)
    loop = asyncio.get_event_loop()

    # --- Begin concurrent file retrieval from commits and localization ---

    async def commit_files():
        responses = []
        all_inferred_files_paths_before_ignore_filter = []
        for match in closest_commit_matches:
            raw_file_paths = await loop.run_in_executor(None, parser.get_files_from_commits, match["oid"])
            commit_file_entries: List[FilePathEntry] = [FilePathEntry(path=fp) for fp in raw_file_paths]
            all_inferred_files_paths_before_ignore_filter.extend(commit_file_entries)
            filtered_commit_file_entries, _ = _filter_and_log_ignored_files(
                commit_file_entries, ignore_files, f"Commit {match['oid']}"
            )
            if filtered_commit_file_entries:
                response = FileSearchResponse(
                    oid=match["oid"],
                    similarity=match["similarity"],
                    file_paths=filtered_commit_file_entries,
                    embedding_model=model,
                    mode=mode.value,
                    path_type='commit'
                )
                responses.append(response)
        logger.info("Inferred files from commits (before ignore filter): %s",
                     [file.path for file in all_inferred_files_paths_before_ignore_filter])
        return responses

    async def localization_files():
        responses = []
        try:
            project_source_dir = os.path.join(DataDir.REPO.get_path(project), "git")

            file_localizer = FileLocalizer(
                problem_statement=prompt,
                root_dir=project_source_dir,
                api_key=llm_model_api_key,
                model=model,
                base_url=str(llm_model_base_url),
                use_mock_llm=False,
                max_tokens=500,
            )

            logger.critical("Starting file localization")
            logger.debug("Starting file localization for prompt: '%s'...", prompt)
            # Pass the project folder name to localize_files to enable summary retrieval
            localized_files_raw, _ = await loop.run_in_executor(
                None, file_localizer.localize_files, project
            )
            logger.debug("File localization completed for prompt '%s', found %d file(s)", prompt, len(localized_files_raw))
            localized_file_entries_unfiltered = [FilePathEntry(path=fp) for fp in localized_files_raw]
            logger.debug("Inferred files from localization (before ignore filter): %s",
                         [entry.path for entry in localized_file_entries_unfiltered])

            filtered_localized_entries, _ = _filter_and_log_ignored_files(
                localized_file_entries_unfiltered, ignore_files, "Localization"
            )

            if filtered_localized_entries:
                localized_response = FileSearchResponse(
                    oid="file_localizer",
                    similarity=0.0,
                    file_paths=filtered_localized_entries,
                    embedding_model=model,
                    mode=mode.value,
                    path_type='localization'
                )
                responses.append(localized_response)

        except Exception as e:
            logger.error("Error during file localization for prompt '%s'", prompt, exc_info=True)
            logger.critical("File localization failed for prompt '%s'", prompt)
            return []
        return responses

    # Launch both paths concurrently
    commit_task = commit_files()
    localization_task = localization_files()
    commit_responses, loc_responses = await asyncio.gather(commit_task, localization_task)

    final_responses = commit_responses + loc_responses

    # Log combined *final* file paths after all filtering
    final_inferred_paths = []
    for resp in final_responses:
        final_inferred_paths.extend([entry.path for entry in resp.file_paths])
    logger.debug("Combined inferred files (after ignore filter): %s", final_inferred_paths)

    return final_responses
