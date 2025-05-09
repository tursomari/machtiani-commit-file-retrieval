import os
import asyncio
import json
import logging
from typing import Optional, Callable, Union, Dict

logger = logging.getLogger(__name__)

class LoggedError(Exception):
    """Exception for errors that have been logged."""

    def __init__(self, message: str, project_name: str):
        self.message = message
        self.project_name = project_name
        super().__init__(f"Error in project '{project_name}': {message}")

def reset_logs(project_name: str) -> None:
    """
    Reset (create or clear) the logs.txt file for a specific project.
    This should be called before generating messages for commits.

    Args:
        project_name (str): The name of the project
    """
    from app.utils import DataDir

    logs_path = os.path.join(DataDir.STORE.get_path(project_name), "logs.txt")

    try:
        # Create an empty file (overwrites if exists)
        with open(logs_path, 'w') as file:
            pass
        logger.info(f"Reset logs for project {project_name}")
    except Exception as e:
        logger.error(f"Error resetting logs for project {project_name}: {e}")


def log_error(error_message: str, project_name: str) -> None:
    """
    Write an error message to the logs.txt file for a specific project and return an error.
    This should be called if there are any errors during generating messages for commits.

    Args:
        error_message (str): The error message to write
        project_name (str): The name of the project

    Raises:
        LoggedError: After logging the error, an exception is raised to fail fast.
    """
    from app.utils import DataDir

    logs_path = os.path.join(DataDir.STORE.get_path(project_name), "logs.txt")

    try:
        with open(logs_path, 'w') as file:
            file.write(f"ERROR: {error_message}")
        logger.info(f"Logged error for project {project_name}: {error_message}")
    except Exception as e:
        logger.error(f"Error logging error for project {project_name}: {e}")

    # Raise after logging to ensure the error propagates
    raise LoggedError(error_message, project_name)

def read_logs(project_name: str) -> Optional[str]:
    """
    Read the contents of the logs.txt file for a specific project.

    Args:
        project_name (str): The name of the project

    Returns:
        Optional[str]: The contents of the logs file, or None if the file doesn't exist or is empty
    """
    from app.utils import DataDir

    logs_path = os.path.join(DataDir.STORE.get_path(project_name), "logs.txt")

    if not os.path.exists(logs_path):
        return None

    try:
        with open(logs_path, 'r') as file:
            content = file.read()
            # Return None if the file is empty (no errors)

        return content if content.strip() else None
    except Exception as e:
        logger.error(f"Error reading logs for project {project_name}: {e}")
        return None


class LogsStatus:
    """Class to handle writing and reading structured status logs."""

    def __init__(self, project_name: str):
        from app.utils import DataDir
        self.project_name = project_name
        self.status_path = os.path.join(DataDir.STORE.get_path(project_name), "status.json") # Changed to .json
        self._update_task = None
        self._running = False
        self._current_stage_key_for_periodic = None # To track stage for periodic updates
        self.status_file_lock = asyncio.Lock() # For safe async read/write

    async def set_overall_status(self, status: str, error_message: Optional[str] = None):
        """Set the overall status of the operation."""
        async with self.status_file_lock:
            status_data = await self._read_status_json()
            status_data["status"] = status
            if error_message:
                status_data["error"] = error_message
            await self._write_status_json(status_data)
        logger.info(f"Set overall status to '{status}' for project {self.project_name}.")

    def _default_status_structure(self) -> Dict:
        return {"overall_progress": 0, "active_stage": None, "stages": {}}

    async def _read_status_json(self) -> Dict:
        if not os.path.exists(self.status_path):
            return self._default_status_structure()
        try:
            # Non-blocking read without re-acquiring the lock
            content = await asyncio.to_thread(self._sync_read_file)
            if content:
                return json.loads(content)
            return self._default_status_structure()
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Could not read or parse status.json for {self.project_name}: {e}. Returning default structure.")
            return self._default_status_structure()
        except Exception as e:
            logger.error(f"Unexpected error reading status.json for {self.project_name}: {e}", exc_info=True)
            return self._default_status_structure()

    def _sync_read_file(self) -> Optional[str]:
        # Synchronous part of reading, to be run in a thread
        if not os.path.exists(self.status_path):
            return None
        with open(self.status_path, 'r') as f:
            return f.read()

    async def _write_status_json(self, data: Dict):
        # Single-threaded write to temp + atomic replace, lock is held by caller
        temp_path = self.status_path + ".tmp"
        try:
            await asyncio.to_thread(self._sync_write_file, data, temp_path)
            await asyncio.to_thread(os.replace, temp_path, self.status_path)
        except Exception as e:
            logger.error(f"Error writing status to {self.status_path} for project {self.project_name}: {e}", exc_info=True)
        finally:
            # Clean up temp file if anything went wrong
            if await asyncio.to_thread(os.path.exists, temp_path):
                await asyncio.to_thread(os.remove, temp_path)

    def _sync_write_file(self, data: Dict, path: str):
        # Synchronous part of writing
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


    async def reset_status(self, stages_config: Optional[Dict[str, str]] = None):
        """
        Reset the status.json file for the project.
        stages_config: A dictionary where keys are stage IDs and values are descriptions.
                       e.g., {"stage_one": "Description for Stage One"}
        """
        status_data = self._default_status_structure()
        if stages_config:
            for key, desc in stages_config.items():
                status_data["stages"][key] = {
                    "description": desc,
                    "status": "pending", # "pending", "in_progress", "completed", "failed"
                    "progress": 0,
                    "error": None
                }
            if stages_config: # Set the first stage as active if any stages are defined
                first_stage_key = list(stages_config.keys())[0]
                status_data["active_stage"] = first_stage_key
                # status_data["stages"][first_stage_key]["status"] = "in_progress" # Optionally set to in_progress here or let set_active_stage handle

        await self._write_status_json(status_data)
        logger.info(f"Reset status for project {self.project_name} with stages: {list(stages_config.keys()) if stages_config else 'None'}")

    async def set_active_stage(self, stage_key: str, overall_progress_val: Optional[int] = None):
        async with self.status_file_lock:
            status_data = await self._read_status_json() # Must be awaited now
            if stage_key not in status_data.get("stages", {}):
                logger.error(f"Stage key '{stage_key}' not found in status configuration for project {self.project_name}.")
                # Consider creating the stage if it's dynamically added, or ensure it's pre-configured.
                # For now, we'll assume it must exist from reset_status.
                # status_data.setdefault("stages", {})[stage_key] = {"description": "Dynamically added", "status": "pending", "progress": 0, "error": None}
                # logger.warning(f"Dynamically added stage '{stage_key}' to status for project {self.project_name}.")
                return # Or raise an error if stages must be pre-defined

            status_data["active_stage"] = stage_key

            # Mark other 'in_progress' stages as 'pending' or 'paused' if needed
            for s_key, s_info in status_data["stages"].items():
                if s_info.get("status") == "in_progress" and s_key != stage_key:
                    # This logic might be too aggressive if you intend to show multiple active sub-tasks.
                    # For now, assuming one primary active stage.
                    logger.info(f"Marking previously active stage '{s_key}' as 'pending' due to new active stage '{stage_key}'.")
                    s_info["status"] = "pending"

            current_stage_info = status_data["stages"][stage_key]
            current_stage_info["status"] = "in_progress"
            if current_stage_info.get("progress", 0) >= 100 : # If reactivating a completed stage
                 current_stage_info["progress"] = 0 # Reset progress for new attempt

            if overall_progress_val is not None:
                status_data["overall_progress"] = max(0, min(100, overall_progress_val))
            else: # Auto-calculate overall progress if not provided
                status_data["overall_progress"] = self._calculate_overall_progress(status_data.get("stages", {}))


            await self._write_status_json(status_data)
        logger.info(f"Set active stage to '{stage_key}' for project {self.project_name}.")

    async def update_stage_progress(self, stage_key: str, progress: int, overall_progress_val: Optional[int] = None):
        async with self.status_file_lock:
            status_data = await self._read_status_json()
            stages = status_data.get("stages", {})
            if stage_key not in stages:
                logger.warning(f"Stage key '{stage_key}' not found during progress update for {self.project_name}. Update ignored.")
                return

            stage_info = stages[stage_key]
            stage_info["progress"] = max(0, min(100, int(progress)))

            if stage_info.get("status") not in ["completed", "failed"]:
                stage_info["status"] = "in_progress" if progress < 100 else "completed"

            if progress == 100 and stage_info.get("status") != "failed": # Ensure completed status if 100% and not failed
                stage_info["status"] = "completed"


            if overall_progress_val is not None:
                status_data["overall_progress"] = max(0, min(100, overall_progress_val))
            else:
                status_data["overall_progress"] = self._calculate_overall_progress(stages)

            await self._write_status_json(status_data)
        logger.debug(f"Updated progress for stage '{stage_key}' to {progress}% for project {self.project_name}.")

    async def mark_stage_status(self, stage_key: str, new_status: str, error: Optional[str] = None, overall_progress_val: Optional[int] = None):
        async with self.status_file_lock:
            status_data = await self._read_status_json()
            stages = status_data.get("stages", {})
            if stage_key not in stages:
                logger.error(f"Stage key '{stage_key}' not found for status mark in {self.project_name}. Status mark ignored.")
                return

            stage_info = stages[stage_key]
            stage_info["status"] = new_status
            if new_status == "completed":
                stage_info["progress"] = 100
                stage_info["error"] = None
            elif new_status == "failed":
                stage_info["error"] = error if error else "Unknown error"
                # Optionally, do not reset progress to 0 on failure, keep last known progress.
            elif new_status == "pending":
                # stage_info["progress"] = 0 # Optionally reset progress if moved back to pending
                pass


            if overall_progress_val is not None:
                status_data["overall_progress"] = max(0, min(100, overall_progress_val))
            else:
                status_data["overall_progress"] = self._calculate_overall_progress(stages)

            await self._write_status_json(status_data)
        logger.info(f"Marked stage '{stage_key}' as '{new_status}' for project {self.project_name}.")


    def _calculate_overall_progress(self, stages_data: Dict) -> int:
        if not stages_data:
            return 0

        num_stages = len(stages_data)
        if num_stages == 0:
            return 0

        total_weighted_progress = 0
        # Simple average of stage progresses for now
        # Could be weighted if stages have different "sizes"
        for stage_info in stages_data.values():
            total_weighted_progress += stage_info.get("progress", 0)

        return int(min(100, round(total_weighted_progress / num_stages)))


    async def update_overall_progress_only(self, overall_progress: int):
        async with self.status_file_lock:
            status_data = await self._read_status_json()
            status_data["overall_progress"] = max(0, min(100, int(overall_progress)))
            await self._write_status_json(status_data)
        logger.info(f"Overall progress for {self.project_name} directly set to {overall_progress}%.")

    async def read_status_async(self) -> Optional[Dict]:
        return await self._read_status_json()

    async def start_periodic_updates(
        self,
        stage_key: str,
        progress_func: Callable[[], Union[int, float]],
        interval: float = 1.0,
        overall_calculator: Optional[Callable[[Dict], int]] = None,
    ):
        if self._running:
            logger.warning(f"Periodic updates already running for {self.project_name}, stage {self._current_stage_key_for_periodic}. New request for {stage_key} ignored.")
            return

        self._running = True
        self._current_stage_key_for_periodic = stage_key
        logger.info(f"Attempting to start periodic updates for project {self.project_name}, stage {stage_key}")


        async def update_loop():
            try:
                while self._running:
                    current_stage_pg = progress_func()
                    async with self.status_file_lock:
                        status_data = await self._read_status_json() # Use async read inside lock
                        stages = status_data.get("stages", {})
                        if stage_key not in stages:
                            logger.warning(f"Periodic update: Stage '{stage_key}' not found for {self.project_name}. Stopping loop.")
                            self._running = False
                            break

                        stage_info = stages[stage_key]
                        stage_info["progress"] = max(0, min(100, int(current_stage_pg)))
                        if stage_info.get("status") not in ["completed", "failed"]: # Only update to in_progress if not terminal
                             stage_info["status"] = "in_progress"

                        if overall_calculator: # If a custom calculator is provided
                            status_data["overall_progress"] = overall_calculator(status_data)
                        else: # Default calculation
                            status_data["overall_progress"] = self._calculate_overall_progress(stages)

                        await self._write_status_json(status_data)

                    logger.debug(f"Periodic status update for stage '{stage_key}' ({self.project_name}): {current_stage_pg}%")
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info(f"Update loop for stage {stage_key} ({self.project_name}) was cancelled.")
            except Exception as e:
                logger.error(f"Error in status update loop for stage {stage_key} ({self.project_name}): {e}", exc_info=True)
            finally:
                logger.info(f"Update loop for stage {stage_key} ({self.project_name}) ended.")
                self._running = False # Ensure running is false when loop exits

        self._update_task = asyncio.create_task(update_loop())
        logger.info(f"Started periodic status update task for project {self.project_name}, stage {stage_key}")


    async def stop_periodic_updates(self, stage_key: str, success: bool = True, overall_calculator: Optional[Callable[[Dict], int]] = None):
        if not self._running and self._update_task is None:
            logger.info(f"Periodic updates for stage {stage_key} ({self.project_name}) not running or already stopped.")
            return

        self._running = False # Signal the loop to stop
        logger.info(f"Stopping periodic status updates for project {self.project_name}, stage {stage_key}")

        if self._update_task:
            try:
                if not self._update_task.done():
                    self._update_task.cancel()
                await self._update_task # Wait for it to finish or be cancelled
            except asyncio.CancelledError:
                logger.info(f"Periodic update task for stage {stage_key} ({self.project_name}) was successfully cancelled during stop.")
            except Exception as e:
                logger.error(f"Error waiting for periodic update task for stage {stage_key} ({self.project_name}) to complete: {e}", exc_info=True)
            finally:
                self._update_task = None

        # Final update for the stage being stopped
        async with self.status_file_lock:
            status_data = await self._read_status_json()
            stages = status_data.get("stages", {})
            if stage_key in stages:
                final_progress = 100 if success else stages[stage_key].get("progress", 0)
                # Determine final status carefully
                if success:
                    final_status = "completed"
                elif stages[stage_key].get("status") == "completed": # If already marked completed by another path
                    final_status = "completed"
                else: # Failed or stopped prematurely
                    final_status = "failed"


                stages[stage_key]["progress"] = final_progress
                stages[stage_key]["status"] = final_status
                if not success and stages[stage_key].get("error") is None: # Add a generic error if one isn't set
                     stages[stage_key]["error"] = "Operation for this stage was stopped or failed."

                if overall_calculator:
                    status_data["overall_progress"] = overall_calculator(status_data)
                else:
                    status_data["overall_progress"] = self._calculate_overall_progress(stages)

                await self._write_status_json(status_data)
        logger.info(f"Final status for stage '{stage_key}' ({self.project_name}) set to '{stages.get(stage_key,{}).get('status')}' with progress {stages.get(stage_key,{}).get('progress')}%.")
        self._current_stage_key_for_periodic = None


# --- Standalone helper functions ---
# These functions provide async interfaces for project status operations

async def initialize_project_status(project_name: str, stages_config: Dict[str, str]):
    """Initializes or resets the project's status.json with defined stages."""
    await LogsStatus(project_name).reset_status(stages_config)

async def read_project_status(project_name: str) -> Optional[Dict]:
    """Reads the structured status from status.json."""
    return await LogsStatus(project_name).read_status_async()

# Synchronous wrapper functions - AVOID using these in async contexts
# These are kept for backwards compatibility with synchronous code

def reset_status(project_name: str,
                 stages_config: Optional[Dict[str, str]] = None) -> None:
    """
    DEPRECATED: Use async methods directly in FastAPI context.
    This synchronous wrapper should only be used in synchronous code paths.

    In async code, use:
    logs_status = LogsStatus(project_name)
    await logs_status.reset_status(stages_config)
    """
    try:
        loop = asyncio.get_running_loop()
        # Running inside an event‑loop – delegate correctly
        return asyncio.create_task(
            LogsStatus(project_name).reset_status(stages_config)
        )
    except RuntimeError:
        # No loop running – old synchronous behaviour
        loop = asyncio.new_event_loop()
        loop.run_until_complete(LogsStatus(project_name).reset_status(stages_config))
        loop.close()

def update_status(project_name: str,
                 stage_key: str,
                 progress: int) -> None:
    """
    DEPRECATED: Use async methods directly in FastAPI context.
    This synchronous wrapper should only be used in synchronous code paths.

    In async code, use:
    logs_status = LogsStatus(project_name)
    await logs_status.update_stage_progress(stage_key, progress)
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(LogsStatus(project_name).update_stage_progress(stage_key, progress))
    finally:
        loop.close()

def read_status(project_name: str) -> Optional[Dict]:
    """
    DEPRECATED: Use async methods directly in FastAPI context.
    This synchronous wrapper should only be used in synchronous code paths.

    In async code, use:
    logs_status = LogsStatus(project_name)
    status_data = await logs_status.read_status_async()
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(LogsStatus(project_name).read_status_async())
    finally:
        loop.close()
