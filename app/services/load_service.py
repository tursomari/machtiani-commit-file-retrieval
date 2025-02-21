import os
import asyncio
import logging
from app.models.requests import LoadRequest  # Import LoadRequest model
from lib.vcs.git_commit_manager import GitCommitManager
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.indexer.file_summary_indexer import FileSummaryEmbeddingGenerator
from lib.utils.utilities import (
    read_json_file,
    write_json_file,
    get_lock_file_path,
    is_locked,
    acquire_lock,
    release_lock,
)
from app.utils import DataDir

logger = logging.getLogger(__name__)

async def load_project_data(load_request: LoadRequest):  # Change to LoadRequest
    openai_api_key = load_request.openai_api_key
    project = load_request.project_name
    ignore_files = load_request.ignore_files or []

    git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")

    lock_file_path = get_lock_file_path(project)
    lock_file_exists, lock_time_duration = await is_locked(lock_file_path)

    if lock_file_exists:
        elapsed_hours = int(lock_time_duration // 3600)
        elapsed_minutes = int((lock_time_duration % 3600) // 60)
        raise RuntimeError(f"Operation is locked for project '{project}'. Please try again later. Lock has been active for {elapsed_hours} hours and {elapsed_minutes} minutes.")

    await acquire_lock(lock_file_path)

    try:
        async def read_commits_logs():
            return await asyncio.to_thread(read_json_file, commits_logs_file_path)

        commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)

        parser = GitCommitManager(commits_logs_json, project)
        depth = 1000
        logger.info("Adding commits to log...")
        await parser.add_commits_to_log(git_project_path, depth)

        # amplify_commits will add extra commits and correspsonding embeddings.
        #await parser.amplify_commits()

        logger.info("Finished adding commits to log.")

        logger.info(f"New commits added: {parser.commits}")
        await asyncio.to_thread(write_json_file, parser.commits, commits_logs_file_path)

        commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
        logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")

        # Reload the updated commits logs
        commits_logs_json = await read_commits_logs()

        existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path) or {}

        generator = CommitEmbeddingGenerator(commits_logs_json, openai_api_key, existing_commits_embeddings_json)
        updated_commits_embeddings_json, new_commit_oids = await asyncio.to_thread(generator.generate_embeddings)

        logger.info(f"Number of new commit OIDs: {len(new_commit_oids)}")

        files_embeddings_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project), "files_embeddings.json")
        logger.info(f"{project}'s embedded files logs file path: {files_embeddings_file_path}")

        existing_files_embeddings_json = await asyncio.to_thread(read_json_file, files_embeddings_file_path)

        # Initialize FileSummaryEmbeddingGenerator with the list of new commit OIDs
        file_summary_generator = FileSummaryEmbeddingGenerator(
            project_name=project,
            commit_logs=commits_logs_json,
            new_commit_oids=new_commit_oids,  # Pass the list of new commit OIDs
            api_key=openai_api_key,
            git_project_path=git_project_path,
            ignore_files=ignore_files,
            existing_file_embeddings=existing_files_embeddings_json
        )

        updated_files_embeddings_json = await asyncio.to_thread(file_summary_generator.generate_embeddings)
        # generating file summary already writes the file.
        #await asyncio.to_thread(write_json_file, updated_files_embeddings_json, files_embeddings_file_path)

        await asyncio.to_thread(write_json_file, updated_commits_embeddings_json, commits_embeddings_file_path)

    finally:
        await release_lock(lock_file_path)

