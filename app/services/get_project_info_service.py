from lib.vcs.repo_manager import get_repo_info_async

async def fetch_project_info(project: str, api_key: str):
    """ Fetch project information including the remote URL and the current git branch. """
    return await get_repo_info_async(project, api_key)
