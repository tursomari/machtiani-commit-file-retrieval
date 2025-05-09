import asyncio
import logging
from typing import Optional
from pydantic import SecretStr, HttpUrl
from app.utils import DataDir
from lib.vcs.repo_manager import (
    get_repo_info_async,
    check_push_access,
)
from lib.utils.utilities import (
    url_to_folder_name,
    is_locked,
    get_lock_file_path,
)

# from lib.utils.log_utils import read_logs, read_status # Old
from lib.utils.log_utils import read_logs, read_project_status # New

logger = logging.getLogger(__name__)


async def status_service(
    codehost_url: HttpUrl,
):
    project_name = url_to_folder_name(str(codehost_url))
    repo_info = await get_repo_info_async(str(codehost_url))
    lock_file_path = get_lock_file_path(project_name)
    lock_file_exists, lock_time_duration = await is_locked(lock_file_path)
    error_logs = read_logs(project_name) # This remains synchronous as per its definition

    # Get current progress status (now a detailed dictionary)
    current_progress_details = await read_project_status(project_name) # Changed

    result = {
        "lock_file_present": lock_file_exists,
        "lock_time_duration": lock_time_duration
    }

    if current_progress_details is not None:
        result["progress"] = current_progress_details # Changed: "progress" now holds the detailed object

    if error_logs:
        result["error_logs"] = error_logs
    return result
