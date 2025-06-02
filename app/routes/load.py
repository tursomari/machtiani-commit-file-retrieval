import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.models.requests import LoadRequest
from app.services.load_service import load_project_data
from git import Repo
import os
from app.utils import DataDir
from lib.utils.utilities import read_json_file # <-- Import the file reader

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/load/")
@router.post("/load")
async def handle_load(load_request: LoadRequest):
    repo = None
    original_head = load_request.head

    try:
        project = load_request.project_name
        git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
        repo = Repo(git_project_path)

        repo.git.checkout(original_head)

        # 1. Get commits from newest to oldest (standard git log behavior)
        commit_iterator = repo.iter_commits(original_head, max_count=load_request.depth_level)
        all_commits_newest_first = list(commit_iterator)

        if not all_commits_newest_first:
            logger.warning("No commits to process for the given specifications.")
            return {"status": True, "message": "No commits to process."}

        # 2. Reverse the list to get commits in chronological order (oldest to newest)
        all_commits_to_process = list(reversed(all_commits_newest_first))
        total_commits_in_range = len(all_commits_to_process)

        # --- START of new logic ---

        # If using a mock LLM, process everything in a single go to speed up testing/dev.
        if load_request.use_mock_llm:
            logger.critical(
                f"use_mock_llm is true. Processing all {total_commits_in_range} commits in a single operation."
            )
            # The original load_request already specifies the correct head and depth
            await load_project_data(load_request)
            logger.critical(f"Finished processing all {total_commits_in_range} commits (mock LLM mode).")
            return {
                "status": True,
                "message": f"Completed processing {total_commits_in_range} commits in a single batch (mock LLM mode).",
            }

        # --- Real LLM processing with two phases: catch-up and new ---

        # Read existing commits to determine which ones are new
        commits_logs_path = os.path.join(DataDir.COMMITS_LOGS.get_path(project), "commits_logs.json")
        commits_logs_json = read_json_file(commits_logs_path) or []
        seen_commit_shas = {commit['oid'] for commit in commits_logs_json}

        # Partition commits into "already seen" and "new"
        previously_processed_commits = []
        new_commits_to_process = []
        for commit in all_commits_to_process:
            if commit.hexsha in seen_commit_shas:
                previously_processed_commits.append(commit)
            else:
                new_commits_to_process.append(commit)

        # Phase 1: Process already-seen commits in one go (no batching needed)
        if previously_processed_commits:
            num_seen = len(previously_processed_commits)
            logger.critical(
                f"Found {num_seen} previously processed commits. Running them in a single fast-forward batch."
            )
            catch_up_head_commit = previously_processed_commits[-1]
            catch_up_request = load_request.copy(deep=True)
            catch_up_request.head = catch_up_head_commit.hexsha
            catch_up_request.depth_level = num_seen

            await load_project_data(catch_up_request)
            logger.critical(f"Completed processing {num_seen} previously seen commits.")
        else:
            logger.info("No previously processed commits found in the requested range.")

        # Phase 2: Process new commits in batches
        if new_commits_to_process:
            total_new_commits = len(new_commits_to_process)
            BATCH_SIZE = load_request.llm_threads
            total_batches = (total_new_commits + BATCH_SIZE - 1) // BATCH_SIZE

            logger.critical(
                f"Beginning chronological processing of {total_new_commits} new commits in {total_batches} batches."
            )

            for batch_num in range(total_batches):
                start_index = batch_num * BATCH_SIZE
                end_index = start_index + BATCH_SIZE
                current_batch_commits = new_commits_to_process[start_index:end_index]

                if not current_batch_commits:
                    continue

                batch_head_commit = current_batch_commits[-1]
                batch_head_sha = batch_head_commit.hexsha
                batch_depth = len(current_batch_commits)

                # The commit range string should be based on the index within the *new* commits list
                commit_range_str = f"new commits {start_index + 1}-{min(end_index, total_new_commits)} of {total_new_commits}"
                logger.critical(
                    f"Processing batch {batch_num + 1}/{total_batches} ({commit_range_str}): "
                    f"Head: {batch_head_sha[:8]}, Depth: {batch_depth}"
                )

                batch_request = load_request.copy(deep=True)
                batch_request.head = batch_head_sha
                batch_request.depth_level = batch_depth

                await load_project_data(batch_request)
                logger.critical(f"Completed batch {batch_num + 1}/{total_batches}.")

            logger.critical(f"Finished chronological processing of all {total_new_commits} new commits.")
        else:
            logger.info("No new commits to process.")

        # --- END of new logic ---

        return {"status": True, "message": f"Completed processing {len(previously_processed_commits)} seen commits and {len(new_commits_to_process)} new commits."}

    except Exception as e:
        logger.error(f"An error occurred during the load process: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if repo and repo.head.commit.hexsha != original_head:
            try:
                logger.info(f"Restoring repository to original HEAD: {original_head}")
                repo.git.checkout(original_head)
            except Exception as checkout_error:
                logger.error(f"CRITICAL: Failed to restore repository to original HEAD: {checkout_error}")


