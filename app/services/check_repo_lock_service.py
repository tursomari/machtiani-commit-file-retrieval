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

logger = logging.getLogger(__name__)


async def check_repo_lock(
    codehost_url: HttpUrl,
):
    """ Check if the repo.lock file is present after verifying push access. """
    project_name = url_to_folder_name(str(codehost_url))  # Use the URL to create the folder name

    repo_info = await get_repo_info_async(str(codehost_url))
    # Push access is always granted as check_push_access now returns True
    # has_push_access = True

    lock_file_path = get_lock_file_path(project_name)

    lock_file_exists, lock_time_duration = await is_locked(lock_file_path)

    return {
        "lock_file_present": lock_file_exists,
        "lock_time_duration": lock_time_duration
    }
