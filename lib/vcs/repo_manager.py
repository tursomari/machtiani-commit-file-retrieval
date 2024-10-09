from git import Repo, GitCommandError
from app.utils import DataDir
from lib.utils.enums import (
    AddRepositoryRequest,
    DeleteRepositoryRequest,
    VCSType,
)
from fastapi import FastAPI, Query, HTTPException, Body
import os
import asyncio  # Import asyncio
from lib.utils.utilities import parse_github_url, validate_github_auth_url, url_to_folder_name
from pydantic import HttpUrl, SecretStr
from typing import Optional, Union
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
    """
    Asynchronously retrieve the remote URL and current branch of the repository for a given project.

    :param project_name: The name of the project.
    :return: A dictionary with remote URL and current branch.
    """
    _project_name = url_to_folder_name(project_name)
    repo_path = DataDir.REPO.get_path(_project_name)
    git_path = os.path.join(repo_path, "git")

    logger.info(f"get_repo_info_async\nproject_name : {project_name}\nrepo_path: {repo_path}\ngit_path: {git_path}")
    # Check if the git_path exists asynchronously
    if not await async_exists(git_path):
        logger.info("Repository does not exist.")
        raise FileNotFoundError(f"Repository for project '{project_name}' does not exist at path: {git_path}")

    repo = Repo(git_path)
    # Get the remote URL
    remote_url_with_api_key = repo.remotes.origin.url
    logger.info(f"remote_url_with_api_key {remote_url_with_api_key}")
    remote_url, api_key = parse_github_url(remote_url_with_api_key)
    logger.info(f"remote_url {remote_url} api_key{api_key}")

    # Get the current branch
    current_branch = repo.active_branch.name

    return {
        "remote_url": remote_url,
        "current_branch": current_branch,
        "api_key": api_key
    }

def clone_repository(codehost_url: HttpUrl, destination_path: str, project_name: str, api_key: Optional[SecretStr] = None):
    full_path = os.path.join(destination_path, "git")

    try:
        # Convert the HttpUrl to a string
        url_str = str(codehost_url)

        if api_key:
            # Construct the authentication URL with the token
            url_parts = url_str.split("://")
            auth_url = f"{url_parts[0]}://{api_key.get_secret_value()}@{url_parts[1]}"

            # Log the URL for debugging (remove this in production)
            logger.debug(f"Auth URL: {auth_url}")

            # Clone using the authenticated URL
            Repo.clone_from(auth_url, full_path)
        else:
            Repo.clone_from(url_str, full_path)

        logger.info(f"Repository cloned to {full_path}")

    except GitCommandError as e:
        logger.error(f"Failed to clone the repository: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clone the repository: {str(e)}")

def add_repository(data: AddRepositoryRequest):
    codehost_url = data.codehost_url
    project_name = data.project_name
    vcs_type = data.vcs_type
    api_key = data.api_key
    openai_api_key = data.openai_api_key  # Get the OpenAI API key

    if vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{vcs_type}' is not supported.")

    # Create necessary directories
    DataDir.create_all(project_name)
    destination_path = DataDir.REPO.get_path(project_name)

    # Clone the repository using the module, into the 'git' directory
    clone_repository(codehost_url, destination_path, project_name, api_key)

    # Return the openai_api_key with the response for further usage
    return {
        "message": f"{vcs_type} repository added successfully",
        "full_path": f"{destination_path}/{project_name}/repo/git",
        "api_key_provided": bool(api_key),
        "openai_api_key_provided": bool(openai_api_key)
    }

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
        # Remove the entire project directory and its contents
        shutil.rmtree(repo_path)  # This will delete the directory and all its contents
        logger.info(f"Successfully deleted repository for project '{project_name}'.")
    except OSError as e:
        logger.error(f"Error deleting repository for project '{project_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete the repository: {str(e)}")

def fetch_and_checkout_branch(codehost_url: HttpUrl, destination_path: str, project_name: str, branch_name: str, api_key: Optional[SecretStr] = None):
    full_path = os.path.join(destination_path, "git")

    try:
        # If the repository is not already cloned, clone it first
        if not os.path.exists(full_path):
            logger.info(f"Repository not found at {full_path}, cloning now...")
            clone_repository(codehost_url, destination_path, project_name, api_key)

        # Open the repository
        repo = Repo(full_path)
        logger.info(f"Opened repository at {full_path}")

        # Add the directory as a safe directory
        logger.info(f"Adding {full_path} as a safe directory for Git operations")
        repo.git.config('--global', '--add', 'safe.directory', full_path)

        # Handle authentication for fetching and pulling
        url_str = str(codehost_url)

        # Extract the value from api_key if provided and check if it's not None or empty
        api_key_value = api_key.get_secret_value() if api_key and api_key.get_secret_value() else None

        if api_key_value:
            # Construct the authentication URL with the token
            url_parts = url_str.split("://")
            auth_url = f"{url_parts[0]}://{api_key_value}@{url_parts[1]}"
            if not validate_github_auth_url(auth_url):
                logger.debug(f"{auth_url} is an invalid authorized url")
                raise HTTPException(status_code=400, detail="Invalid Authorized GitHub URL format.")

            # Set the authenticated URL for the remote
            repo.remotes.origin.set_url(auth_url)
            logger.debug(f"Auth URL set for fetch and pull: {auth_url}")
        else:
            # Ensure we set the original URL if no valid API key is provided
            repo.remotes.origin.set_url(url_str)

        # Fetch the latest changes from the remote
        logger.info(f"Fetching latest changes from remote for repository at {full_path}")
        repo.remotes.origin.fetch()

        # Check if the local branch is diverged from the remote branch
        local_branch = repo.head.reference
        remote_branch = repo.remotes.origin.refs[branch_name]

        # Compare the local and remote branches
        if local_branch.commit != remote_branch.commit:
            logger.warning(f"Local branch '{branch_name}' has diverged from remote. Performing hard reset.")
            # Perform a hard reset to the remote branch state
            repo.git.reset('--hard', f'origin/{branch_name}')
            logger.info(f"Successfully reset local branch '{branch_name}' to match remote.")

        # Checkout the specified branch
        logger.info(f"Checking out branch '{branch_name}'")
        repo.git.checkout(branch_name)

        # Pull the latest changes for the branch
        logger.info(f"Pulling latest changes for branch '{branch_name}'")
        repo.remotes.origin.pull(branch_name)

        logger.info(f"Checked out and updated to the latest commit on branch {branch_name} in {full_path}")

        # Test push to verify if the user has push access (without actual changes)
        try:
            repo.remotes.origin.push(branch_name)  # Attempt to push without any new commits
            logger.info(f"Push access confirmed for branch '{branch_name}' (no changes)")
        except GitCommandError as e:
            logger.warning(f"Push with no changes failed, user may not have push access: {str(e)}")

    except Exception as e:
        logger.error(f"Error during fetch and checkout process: {e}")
        raise

    except GitCommandError as e:
        logger.error(f"Failed to fetch and checkout branch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch and checkout branch: {str(e)}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
