import os
import asyncio
import logging
from app.models.requests import LoadRequest  # Import LoadRequest model
from lib.vcs.git_commit_manager import GitCommitManager
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.utils.utilities import (
    read_json_file,
    write_json_file,
    get_lock_file_path,
    is_locked,
    acquire_lock,
    release_lock,
    validate_files_embeddings,
    validate_commits_logs,
)
from app.utils import DataDir

logger = logging.getLogger(__name__)

async def load_project_data(load_request: LoadRequest):
    llm_model_api_key = load_request.llm_model_api_key
    llm_model_base_url = load_request.llm_model_base_url
    embeddings_model_api_key = load_request.embeddings_model_api_key
    project = load_request.project_name
    ignore_files = load_request.ignore_files or []
    head = load_request.head
    use_mock_llm = load_request.use_mock_llm or False

    git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    new_commits_file_path = os.path.join(commits_logs_dir_path, "new_commits.json") if use_mock_llm else None

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

        if commits_logs_json:
            try:
                validate_commits_logs(commits_logs_json)
            except AssertionError as e:
                logger.error(f"Commit logs validation error: {e}")
                raise

        parser = GitCommitManager(
            commits_logs_json,
            project,
            llm_model_api_key=llm_model_api_key,
            llm_model_base_url=llm_model_base_url,
            embeddings_model_api_key=embeddings_model_api_key,
            llm_model="gpt-4o-mini",
            ignore_files=ignore_files,
            head=head,
            use_mock_llm=use_mock_llm
        )

        depth = 15000
        logger.info("Adding commits to log...")
        await parser.add_commits_and_summaries_to_log(git_project_path, depth)

        base_prompt = "Based on the diff, create a concise and informative git commit message. Diff details:\n\n"
        # amplify_commits will add extra commits and correspsonding embeddings.
        await parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=False)
        #parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=True)

        logger.info("Finished adding commits to log.")

        # Validate and save commits_logs
        if parser.commits_logs:
            try:
                validate_commits_logs(parser.commits_logs)
            except AssertionError as e:
                logger.error(f"Commit logs validation error: {e}")
                raise

        logger.info(f"New commits added: {parser.commits_logs}")
        await asyncio.to_thread(write_json_file, parser.commits_logs, commits_logs_file_path)

        # Save and validate new_commits if use_mock_llm is True
        if use_mock_llm and parser.new_commits:
            try:
                validate_commits_logs(parser.new_commits)
                await asyncio.to_thread(write_json_file, parser.new_commits, new_commits_file_path)
                logger.info(f"Saved new_commits to {new_commits_file_path}")
            except AssertionError as e:
                logger.error(f"New commits validation error: {e}")
                raise

        commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
        logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")

        # Reload the updated commits logs
        commits_logs_json = await read_commits_logs()

        existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path) or {}

        generator = CommitEmbeddingGenerator(
            commits_logs_json,
            embeddings_model_api_key,
            embeddings_model_base_url=llm_model_base_url,
            existing_commits_embeddings=existing_commits_embeddings_json,
            files_embeddings=parser.summary_cache,
            use_mock_llm=use_mock_llm
        )
        updated_commits_embeddings_json, new_commit_oids = await asyncio.to_thread(generator.generate_embeddings)

        logger.info(f"Number of new commit OIDs: {len(new_commit_oids)}")

        await asyncio.to_thread(write_json_file, updated_commits_embeddings_json, commits_embeddings_file_path)

    finally:
        await release_lock(lock_file_path)

