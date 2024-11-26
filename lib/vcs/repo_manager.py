from git import Repo, Remote, GitCommandError
from app.utils import DataDir
from lib.utils.enums import (
    AddRepositoryRequest,
    VCSType,
)
from fastapi import FastAPI, Query, HTTPException, Body
import os
import asyncio  # Import asyncio
from lib.utils.utilities import (
    parse_github_url,
    validate_github_auth_url,
    url_to_folder_name,
    add_safe_directory,
    construct_remote_url,
)
from app.models.responses import DeleteStoreResponse
from pydantic import HttpUrl, SecretStr
from typing import Optional, Union, Dict
from fastapi import HTTPException
import shutil
import subprocess
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def async_exists(path: str) -> bool:
    """Asynchronously check if a path exists."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, os.path.exists, path)

async def get_repo_info_async(project_name: str):
    _project_name = url_to_folder_name(project_name)
    repo_path = DataDir.REPO.get_path(_project_name)
    git_path = os.path.join(repo_path, "git")

    if not await async_exists(git_path):
        logger.info("Repository does not exist.")
        raise FileNotFoundError(f"Repository for project '{project_name}' does not exist at path: {git_path}")

    repo = Repo(git_path)

    # Check if the repository has an active branch
    current_branch = None
    try:
        current_branch = repo.active_branch.name
    except (AttributeError, TypeError):
        logger.warning("No active branch found, repo might be in a detached HEAD state.")

    return {
        "current_branch": current_branch,  # This will be None if there's no active branch
    }

def clone_repository(
    codehost_url: HttpUrl,
    destination_path: str,
    project_name: str,
    api_key: Optional[SecretStr] = None
):
    full_path = os.path.join(destination_path, "git")

    try:
        remote_url = construct_remote_url(codehost_url, api_key)
        Repo.clone_from(remote_url, full_path)
        logger.info(f"Repository cloned to {full_path}")

        # Log the current remotes after cloning
        repo = Repo(full_path)
        remove_all_remotes(repo)

    except GitCommandError as e:
        logger.error(f"Failed to clone the repository: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone the repository: {str(e)}"
        )
    except ValueError as ve:
        logger.error(f"URL construction error: {str(ve)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid repository URL: {str(ve)}"
        )

def add_repository(data: AddRepositoryRequest):
    codehost_url = data.codehost_url
    project_name = data.project_name
    vcs_type = data.vcs_type
    api_key = data.api_key
    openai_api_key = data.openai_api_key

    if vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{vcs_type}' is not supported.")

    # Create necessary directories
    DataDir.create_all(project_name)
    destination_path = DataDir.REPO.get_path(project_name)

    # Clone the repository using the module, into the 'git' directory
    clone_repository(codehost_url, destination_path, project_name, api_key)

    # Initialize a Git repository in the CONTENT directory
    content_path = DataDir.CONTENT.get_path(project_name)
    if not os.path.exists(content_path):
        os.makedirs(content_path)

    if not os.path.exists(os.path.join(content_path, ".git")):  # Check if a Git repo already exists
        repo = Repo.init(content_path)  # Initialize a new git repository in CONTENT
        logger.info(f"Initialized a new Git repository at {content_path}")

        # Set global Git configuration for user.email and user.name
        repo.git.config('user.email', '')  # Set user email to an empty string
        repo.git.config('user.name', 'machtiani')  # Set user name to "machtiani"

    # Return the openai_api_key with the response for further usage
    return {
        "message": f"{vcs_type} repository added successfully",
        "full_path": f"{destination_path}/{project_name}/repo/git",
        "api_key_provided": bool(api_key),
        "openai_api_key_provided": bool(openai_api_key)
    }

def delete_store(codehost_url: HttpUrl, project_name: str, ignore_files: list, vcs_type: VCSType = VCSType.git, api_key: Optional[SecretStr] = None, openai_api_key: Optional[SecretStr] = None, new_repo: bool = False) -> Dict[str, str]:
    """
    Deletes the specified store and cleans up associated files after checking for push access,
    unless `new_repo` is set to True.

    :param codehost_url: The URL of the code host (e.g., GitHub).
    :param project_name: The name of the project to delete.
    :param ignore_files: List of files to ignore during operations.
    :param vcs_type: The type of version control system (default: git).
    :param api_key: Optional GitHub API key for authentication.
    :param openai_api_key: Optional OpenAI API key for additional operations.
    :param new_repo: If True, skip checking push access before deletion (default: False).
    :return: A message indicating success or failure in deletion.
    """
    project_name = url_to_folder_name(str(codehost_url))  # Use the URL to create the folder name

    store_path = DataDir.STORE.get_path(project_name)

    if not os.path.exists(store_path):
        return DeleteStoreResponse(success=False, message=f"Store for project '{project_name}' does not exist at path: {store_path}")

    # Check for push access before deletion if new_repo is False
    repo_path = DataDir.REPO.get_path(project_name)
    if not os.path.exists(repo_path):
        return DeleteStoreResponse(success=False, message=f"Repository for project '{project_name}' does not exist at path: {repo_path}")

    git_path = os.path.join(repo_path, "git")
    repo = Repo(git_path)
    current_branch = repo.active_branch.name

    # Skip push access check if new_repo is True
    if not new_repo and not check_push_access(codehost_url, repo_path, project_name, current_branch, api_key):
        return DeleteStoreResponse(success=False, message=f"User does not have push access to the branch '{current_branch}'. Deletion aborted.")

    try:
        # Remove the entire project directory and its contents
        shutil.rmtree(store_path)  # This will delete the directory and all its contents
        return DeleteStoreResponse(success=True, message=f"Store for project '{project_name}' deleted successfully.")
    except OSError as e:
        logger.error(f"Error deleting store for project '{project_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete the store: {str(e)}")


def fetch_and_checkout_branch(
    codehost_url: HttpUrl,
    destination_path: str,
    project_name: str,
    branch_name: str,
    api_key: Optional[SecretStr] = None
):
    full_path = os.path.join(destination_path, "git")

    try:
        add_safe_directory(full_path)

        if not os.path.exists(full_path):
            logger.info(f"Repository not found at {full_path}.")
            return

        repo = Repo(full_path)
        remote_url = construct_remote_url(codehost_url, api_key)

        # Check if 'origin' remote exists
        remote_names = [remote.name for remote in repo.remotes]
        if 'origin' in remote_names:
            origin_remote = repo.remote('origin')
        else:
            origin_remote = repo.create_remote('origin', remote_url)
            logger.info("Created new 'origin' remote.")

        # Set the URL for the 'origin' remote
        origin_remote.set_url(remote_url)

        # Log the current remotes after setting the URL
        origin_remote.fetch()

        if branch_name in repo.heads:
            local_branch = repo.heads[branch_name]
            logger.info(f"Local branch '{branch_name}' found.")
        else:
            logger.info(f"Branch '{branch_name}' does not exist locally. Creating and tracking it.")
            # Ensure the branch exists on the remote
            remote_branch_names = [ref.remote_head for ref in origin_remote.refs]
            if branch_name in remote_branch_names:
                remote_branch_ref = origin_remote.refs[branch_name]
                local_branch = repo.create_head(branch_name, remote_branch_ref)
                local_branch.set_tracking_branch(remote_branch_ref)
            else:
                logger.error(f"Branch '{branch_name}' does not exist on the remote.")
                raise Exception(f"Branch '{branch_name}' does not exist on the remote.")

        local_commit = local_branch.commit
        remote_commit = origin_remote.refs[branch_name].commit

        if local_commit != remote_commit:
            logger.info(f"Local branch '{branch_name}' is divergent from remote. Hard resetting to remote.")
            repo.git.reset('--hard', f'origin/{branch_name}')
            logger.info(f"Successfully hard reset local branch '{branch_name}' to match remote.")

        local_branch.checkout()

        logger.info(f"Pulling latest changes for branch '{branch_name}'")
        origin_remote.pull(branch_name)

        repo.git.config('--global', '--add', 'safe.directory', full_path)

        # Remove all remotes after successful fetch and checkout
        remove_all_remotes(repo)

    except GitCommandError as e:
        logger.error(f"Git command failed: {str(e)}")
        raise
    except ValueError as ve:
        logger.error(f"Value error: {str(ve)}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        raise

def delete_repository(project_name: str):
    """
    Deletes the specified repository and cleans up associated files.

    :param project_name: The name of the project to delete.
    :raises ValueError: If the project does not exist.
    """
    repo_path = DataDir.REPO.get_path(project_name)

    if not os.path.exists(repo_path):
        raise ValueError(f"Repository for project '{project_name}' does not exist at path: {repo_path}")

    try:
        # Remove the entire project directory
        os.rmdir(repo_path)  # This will only work if the directory is empty
    except OSError as e:
        logger.error(f"Error deleting repository for project '{project_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete the repository: {str(e)}")

def check_push_access(codehost_url: HttpUrl, destination_path: str, project_name: str, branch_name: str, api_key: Optional[SecretStr] = None) -> bool:
    """
    Check if the user has push access to the specified branch.

    :param repo: The Git repository object.
    :param branch_name: The name of the branch to check.
    :return: True if push access is granted, False otherwise.
    """

    full_path = os.path.join(destination_path, "git")
    url_str = str(codehost_url)

    # Determine the repository path
    git_project_path = os.path.join(DataDir.REPO.get_path(project_name), "git")

    try:
        # Add the repo path as a safe directory
        add_safe_directory(git_project_path)

        if not os.path.exists(full_path):
            logger.info(f"Repository not found at {full_path}")

        # Open the repository
        repo = Repo(full_path)

        remote_url = construct_remote_url(codehost_url, api_key)

        # Check if 'origin' remote exists
        remote_names = [remote.name for remote in repo.remotes]
        if 'origin' in remote_names:
            origin_remote = repo.remote('origin')
        else:
            origin_remote = repo.create_remote('origin', remote_url)
            logger.info("Created new 'origin' remote.")

        # Set the authenticated URL for the remote
        repo.remotes.origin.set_url(remote_url)
        # Test push to verify if the user has push access (without actual changes)
        try:
            repo.remotes.origin.push(branch_name)  # Attempt to push without any new commits
            return True
        except GitCommandError as e:
            logger.warning(f"Push with no changes failed, user may not have push access: {str(e)}")
            return False
        try:
            repo.remotes.origin.push(branch_name)  # Attempt to push without any new commits
            return True
        except GitCommandError as e:
            logger.warning(f"Push with no changes failed, user may not have push access: {str(e)}")
            return False

        remove_all_remotes(repo)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

def check_pull_access(
    codehost_url: HttpUrl,
    destination_path: str,
    project_name: str,
    api_key: Optional[SecretStr] = None
) -> bool:
    """
    Check if the user has pull access to the current branch of the specified repository.

    :param codehost_url: The URL of the code host (e.g., GitHub).
    :param destination_path: The path where the repository is located.
    :param project_name: The name of the project.
    :param api_key: Optional GitHub API key for authentication.
    :return: True if pull access is granted, False otherwise.
    """
    full_path = os.path.join(destination_path, "git")
    url_str = str(codehost_url)
    # Initialize remote_url with url_str
    remote_url = url_str

    # Determine the repository path
    git_project_path = os.path.join(DataDir.REPO.get_path(project_name), "git")

    try:
        # Add the repo path as a safe directory
        add_safe_directory(git_project_path)

        if not os.path.exists(full_path):
            logger.info(f"Repository not found at {full_path}")
            return False

        # Open the repository
        repo = Repo(full_path)

        # Get the current active branch
        current_branch = repo.active_branch.name

        # Check if 'origin' remote exists
        remote_names = [remote.name for remote in repo.remotes]
        if 'origin' in remote_names:
            origin_remote = repo.remote('origin')
            logger.info("Found existing 'origin' remote.")
            # Update the remote URL
            origin_remote.set_url(remote_url)
        else:
            # Create 'origin' remote with remote_url
            origin_remote = repo.create_remote('origin', remote_url)
            logger.info("Created new 'origin' remote.")

        # Test fetch to verify if the user has pull access without API key
        try:
            origin_remote.fetch(current_branch)  # Attempt to fetch the current branch
            return True
        except GitCommandError as e:
            logger.warning(f"Fetch failed without API key: {str(e)}")
            # Update remote_url with API key
            remote_url = construct_remote_url(codehost_url, api_key)
            # Update the 'origin' remote URL
            origin_remote.set_url(remote_url)
            logger.debug(f"Set remote 'origin' URL with API key")

            # Attempt to fetch again with the authenticated URL
            try:
                origin_remote.fetch(current_branch)
                logger.info(f"Pull access confirmed for branch '{current_branch}' with API key")
                return True
            except GitCommandError as e:
                logger.warning(f"Fetch failed with API key: {str(e)}")
                return False

        logger.info("User does not have pull access to the current branch.")
        remove_all_remotes(repo)
        return False

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

def remove_all_remotes(repo: Repo):
    """
    Removes all remotes from the repository.

    Args:
        repo (Repo): The Git repository object.
    """
    try:
        # Get the list of all remote names
        remote_names = [remote.name for remote in repo.remotes]

        # Remove each remote
        for remote_name in remote_names:
            repo.delete_remote(remote_name)

        # Retrieve the updated list of remotes directly
        updated_remotes = [remote.name for remote in Remote.list_items(repo)]

        # Verify that no remotes remain
        if updated_remotes:
            logger.error(f"Some remotes were not removed")
            raise Exception("Failed to remove all remotes.")
        else:
            logger.info("All remotes have been successfully removed.")

    except Exception as e:
        logger.error(f"An error occurred while removing remotes: {str(e)}")
        raise

