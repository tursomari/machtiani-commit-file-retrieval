import os
import asyncio
import logging
from typing import Dict # Corrected from "typing Dict"
from app.models.requests import LoadRequest, AmplificationLevel
from lib.vcs.git_commit_manager import GitCommitManager
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.utils.utilities import (
    read_json_file, write_json_file, get_lock_file_path, is_locked,
    acquire_lock, release_lock, validate_files_embeddings, validate_commits_logs,
)
from app.utils import DataDir
# from lib.utils.log_utils import LogsStatus # Old direct use, will be managed more carefully
from lib.utils.log_utils import LogsStatus, initialize_project_status, log_error as util_log_error

logger = logging.getLogger(__name__)

# Define stage keys consistently
STAGE_ADD_SUMMARIES = "add_commits_and_summaries"
STAGE_AMPLIFICATION = "commit_amplification"
STAGE_EMBEDDINGS = "generate_commit_embeddings"


def _calculate_overall_progress_for_load_service(status_dict_data: dict) -> int:
    # Custom calculation for load_service's overall progress
    # This can be the same as LogsStatus._calculate_overall_progress or more specific
    if not status_dict_data or not status_dict_data.get("stages"):
        return 0
    stages = status_dict_data.get("stages", {})
    num_stages = len(stages)
    if num_stages == 0: return 0

    total_progress = 0
    num_completed = 0
    # active_stage_progress_contribution = 0.0 # This variable was not used after its calculation was commented out

    # Simpler model: average of all stage progresses as per the new logic's return
    all_stage_progress_values = []
    for stage_key, stage_info in stages.items():
        all_stage_progress_values.append(stage_info.get("progress", 0))
        if stage_info.get("status") == "completed":
            num_completed +=1
        elif stage_info.get("status") == "failed":
            num_completed +=1 # Count as "finished" for weighting if this is desired for overall % when one fails

    if not all_stage_progress_values: # if no stages had progress, avoid division by zero
        return 0

    # The patch's logic for overall progress seems to have converged on averaging stage progresses
    # For example:
    # active_stage_contribution = (stage_info.get("progress", 0) / 100.0) * (100.0 / num_stages)
    # overall_p = (num_completed / num_stages) * 100.0 if num_stages > 0 else 0.0
    # return int(min(100, round(overall_p + active_stage_progress_contribution)))
    # The simpler model was: avg_progress = sum(s.get("progress",0) for s in stages.values()) / num_stages if num_stages > 0 else 0
    # The function ultimately returned avg_progress. Let's stick to that for now.
    avg_progress = sum(s.get("progress",0) for s in stages.values()) / num_stages if num_stages > 0 else 0
    return int(min(100, round(avg_progress)))


async def load_project_data(load_request: LoadRequest):
    project = load_request.project_name
    status_manager = LogsStatus(project) # Main status manager for this operation
    current_stage_key_active = None # To track current stage for error handling

    amplification_level = load_request.amplification_level # Used for stage config
    use_mock_llm = load_request.use_mock_llm or False

    # --- Define file paths early ---
    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    mock_commits_logs_file_path = os.path.join(commits_logs_dir_path, "mock_commits_logs.json")
    mock_new_commits_file_path = None
    if use_mock_llm:
        mock_new_commits_file_path = os.path.join(commits_logs_dir_path, "mock_new_commits.json")

    commits_embeddings_dir_path = DataDir.COMMITS_EMBEDDINGS.get_path(project)
    commits_embeddings_file_path = os.path.join(commits_embeddings_dir_path, "commits_embeddings.json")
    mock_commits_embeddings_file_path = os.path.join(commits_embeddings_dir_path, "mock_commits_embeddings.json")


    # --- Stage Configuration ---
    stages_config_template = {
        STAGE_ADD_SUMMARIES: "Stage {idx}/{total}: Adding commits and summaries",
        STAGE_AMPLIFICATION: "Stage {idx}/{total}: Commit amplification",
        STAGE_EMBEDDINGS: "Stage {idx}/{total}: Generating commit embeddings",
    }

    active_stages_keys = [STAGE_ADD_SUMMARIES]
    if amplification_level != AmplificationLevel.OFF:
        active_stages_keys.append(STAGE_AMPLIFICATION)
    active_stages_keys.append(STAGE_EMBEDDINGS)

    total_major_stages = len(active_stages_keys)
    final_stages_config = {}
    for i, key in enumerate(active_stages_keys):
        final_stages_config[key] = stages_config_template[key].format(idx=i+1, total=total_major_stages)

    # --- Lock acquisition ---
    lock_file_path = get_lock_file_path(project)
    lock_file_exists, lock_time_duration = await is_locked(lock_file_path)
    if lock_file_exists:
        elapsed_hours = int(lock_time_duration // 3600)
        elapsed_minutes = int((lock_time_duration % 3600) // 60)
        logger.critical(f"Operation locked for project '{project}'. Lock active for {elapsed_hours}h {elapsed_minutes}m.")
        raise RuntimeError(f"Operation is locked for project '{project}'. Please try again later. Lock has been active for {elapsed_hours} hours and {elapsed_minutes} minutes.")
    await acquire_lock(lock_file_path)

    await initialize_project_status(project, final_stages_config)

    try:
        # --- Initial Commits Logs Read ---
        # commits_logs_file_path is defined above
        async def read_commits_logs_internal():
            return await asyncio.to_thread(read_json_file, commits_logs_file_path)

        commits_logs_json = await read_commits_logs_internal()

        if commits_logs_json: # Validate existing logs if they exist
            try:
                validate_commits_logs(commits_logs_json)
            except AssertionError as e:
                logger.critical(f"Initial commit logs validation error: {e}")
                raise

        parser = GitCommitManager( # Pass necessary args
            commits_logs_json, project, llm_model_api_key=load_request.llm_model_api_key,
            llm_model_base_url=load_request.llm_model_base_url, embeddings_model_api_key=load_request.embeddings_model_api_key,
            llm_model=load_request.llm_model, head=load_request.head, ignore_files=load_request.ignore_files or [],
            use_mock_llm=use_mock_llm, llm_threads=load_request.llm_threads
        )

        # --- Stage 1: Add commits and summaries ---
        if STAGE_ADD_SUMMARIES in final_stages_config:
            current_stage_key_active = STAGE_ADD_SUMMARIES
            await status_manager.set_active_stage(current_stage_key_active, overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
            logger.critical(f"Starting {final_stages_config[current_stage_key_active]} with depth {load_request.depth_level}.")

            await parser.add_commits_and_summaries_to_log(
                os.path.join(DataDir.REPO.get_path(project), "git"),
                load_request.depth_level,
                status_manager_hook=status_manager,
                stage_key_hook=current_stage_key_active,
                overall_progress_calculator_hook=_calculate_overall_progress_for_load_service
            )
            await status_manager.mark_stage_status(current_stage_key_active, "completed", overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
            logger.critical(f"Completed {final_stages_config[current_stage_key_active]}.")

        # --- Stage 2: Commit Amplification ---
        if STAGE_AMPLIFICATION in final_stages_config:
            current_stage_key_active = STAGE_AMPLIFICATION
            await status_manager.set_active_stage(current_stage_key_active, overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
            logger.critical(f"Starting {final_stages_config[current_stage_key_active]} at {amplification_level} level.")

            base_prompt = "Based on the diff, create a concise and informative git commit message. Diff details:\n\n"
            if amplification_level == AmplificationLevel.LOW:
                await parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=False, status_manager_hook=status_manager, stage_key_hook=current_stage_key_active, overall_progress_calculator_hook=_calculate_overall_progress_for_load_service)
            elif amplification_level == AmplificationLevel.MID:
                await parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=False, status_manager_hook=status_manager, stage_key_hook=current_stage_key_active, overall_progress_calculator_hook=_calculate_overall_progress_for_load_service, sub_operation_total_steps=2, current_sub_operation_step=1)
                await parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=True, status_manager_hook=status_manager, stage_key_hook=current_stage_key_active, overall_progress_calculator_hook=_calculate_overall_progress_for_load_service, sub_operation_total_steps=2, current_sub_operation_step=2)
            elif amplification_level == AmplificationLevel.HIGH:
                await parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=False, status_manager_hook=status_manager, stage_key_hook=current_stage_key_active, overall_progress_calculator_hook=_calculate_overall_progress_for_load_service, sub_operation_total_steps=2, current_sub_operation_step=1)
                await parser.amplify_commits(base_prompt=base_prompt, temperature=0.0, per_file=True, status_manager_hook=status_manager, stage_key_hook=current_stage_key_active, overall_progress_calculator_hook=_calculate_overall_progress_for_load_service, sub_operation_total_steps=2, current_sub_operation_step=2)

            await status_manager.mark_stage_status(current_stage_key_active, "completed", overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
            logger.critical(f"Completed {final_stages_config[current_stage_key_active]}.")

        # --- RESTORED: Validation and Saving of Commit Logs ---
        if parser.commits_logs:
            try:
                validate_commits_logs(parser.commits_logs)
            except AssertionError as e:
                logger.critical(f"Processed commits_logs validation error: {e}")
                raise

        if hasattr(parser, 'new_commits') and parser.new_commits: # GitCommitManager might not always have new_commits
            try:
                validate_commits_logs(parser.new_commits)
            except AssertionError as e:
                logger.error(f"New commit logs validation error: {e}") # Was error in original
                raise

        if use_mock_llm:
            await asyncio.to_thread(write_json_file, parser.commits_logs, mock_commits_logs_file_path)
            logger.info(f"Saved mock commits_logs to {mock_commits_logs_file_path}")
            if hasattr(parser, 'new_commits') and parser.new_commits and mock_new_commits_file_path:
                await asyncio.to_thread(write_json_file, parser.new_commits, mock_new_commits_file_path)
                logger.info(f"Saved mock new commits log to {mock_new_commits_file_path}")
        else:
            count_new_commits = len(parser.new_commits) if hasattr(parser, 'new_commits') and isinstance(parser.new_commits, list) else "some"
            logger.info(f"{count_new_commits} new commits processed. Saving main commits_logs.")
            await asyncio.to_thread(write_json_file, parser.commits_logs, commits_logs_file_path)
            logger.info(f"Saved commits_logs to {commits_logs_file_path}")


        # --- Stage 3: Generating Commit Embeddings ---
        if STAGE_EMBEDDINGS in final_stages_config:
            current_stage_key_active = STAGE_EMBEDDINGS
            await status_manager.set_active_stage(current_stage_key_active, overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
            logger.critical(f"Starting {final_stages_config[current_stage_key_active]}.")

            # commits_embeddings_file_path and mock_commits_embeddings_file_path defined at the top
            # Re-read commit logs from disk to ensure consistency if they were modified and saved by previous stages.
            # Or, if parser.commits_logs is guaranteed to be the final version, it can be used directly.
            # The original re-read it, so let's maintain that.
            commits_logs_json_for_embedding = await read_commits_logs_internal()
            if not commits_logs_json_for_embedding:
                logger.warning("No commit logs found for embedding stage. Skipping.") # Or raise error
                # Mark as complete if skipped due to no data
                await status_manager.mark_stage_status(
                    current_stage_key_active,
                    "completed",
                    overall_progress_val=_calculate_overall_progress_for_load_service(
                        await status_manager.read_status_async()
                    )
                )
                logger.critical(
                    f"Completed {final_stages_config[current_stage_key_active]} (skipped due to no data)."
                )
            else:
                existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path) or {}
                files_embeddings_for_generator = parser.summary_cache # This should be populated from stage 1

                generator = CommitEmbeddingGenerator(
                    commits_logs_json_for_embedding, load_request.embeddings_model_api_key,
                    embeddings_model_base_url=load_request.llm_model_base_url,
                    existing_commits_embeddings=existing_commits_embeddings_json,
                    files_embeddings=files_embeddings_for_generator, use_mock_llm=use_mock_llm
                )

                await status_manager.update_stage_progress(current_stage_key_active, 0, overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
                # Assuming generate_embeddings might take time and could internally update fine-grained progress if refactored.
                # For now, we get the result and then mark complete.
                updated_commits_embeddings_json, new_commit_oids = await asyncio.to_thread(generator.generate_embeddings)

                logger.info(f"Number of new commit OIDs for embeddings: {len(new_commit_oids)}") # RESTORED logging

                # --- RESTORED: Saving of Commit Embeddings ---
                if use_mock_llm:
                    await asyncio.to_thread(write_json_file, updated_commits_embeddings_json, mock_commits_embeddings_file_path)
                    logger.info(f"Saved mock commit embeddings to {mock_commits_embeddings_file_path}")
                else:
                    await asyncio.to_thread(write_json_file, updated_commits_embeddings_json, commits_embeddings_file_path)
                    logger.info(f"Saved commit embeddings to {commits_embeddings_file_path}")

                await status_manager.mark_stage_status(current_stage_key_active, "completed", overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async()))
                logger.critical(f"Completed {final_stages_config[current_stage_key_active]}.")

        # Final overall progress update
        current_status = await status_manager.read_status_async()
        all_stages_done = True
        # Check against active_stages_keys which are the ones actually configured to run
        for key in active_stages_keys:
            if current_status.get("stages", {}).get(key, {}).get("status") != "completed":
                all_stages_done = False
                logger.warning(f"Stage {key} was not marked completed by end of load_project_data. Status: {current_status.get('stages', {}).get(key, {}).get('status')}")

        if all_stages_done:
            await status_manager.update_overall_progress_only(100)
            logger.info("All stages completed successfully. Overall progress set to 100%.")
        else:
            final_progress = _calculate_overall_progress_for_load_service(await status_manager.read_status_async())
            await status_manager.update_overall_progress_only(final_progress)
            logger.warning(f"Not all configured stages completed. Final overall progress calculated to {final_progress}%.")


    except Exception as e:
        logger.critical(f"Operation failed during stage '{current_stage_key_active or 'initialization'}': {e}", exc_info=True)
        if current_stage_key_active and current_stage_key_active in final_stages_config:
            await status_manager.mark_stage_status(
                current_stage_key_active, "failed", error=str(e),
                overall_progress_val=_calculate_overall_progress_for_load_service(await status_manager.read_status_async())
            )
        # Ensure overall progress reflects the failure appropriately
        final_progress_on_error = _calculate_overall_progress_for_load_service(await status_manager.read_status_async())
        await status_manager.update_overall_progress_only(final_progress_on_error)
        await status_manager.set_overall_status("failed", error_message=str(e)) # Also mark overall status as failed

        util_log_error(f"Operation failed in stage {current_stage_key_active or 'UNKNOWN'}: {str(e)}", project)
        raise # Re-raise the exception to be caught by the route handler
    finally:
        await release_lock(lock_file_path)
