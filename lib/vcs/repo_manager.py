from git import Repo, GitCommandError
from app.utils import DataDir
from lib.utils.utilities import parse_github_url
from pydantic import HttpUrl, SecretStr
from typing import Optional, Union
from fastapi import HTTPException
import os
import subprocess
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_repo_info(project_name: str):
    """
    Retrieve the remote URL and current branch of the repository for a given project.

    :param project_name: The name of the project.
    :return: A dictionary with remote URL and current branch.
    """
    repo_path = DataDir.REPO.get_path(project_name)
    git_path = os.path.join(repo_path, "git")

    if not os.path.exists(git_path):
        raise FileNotFoundError(f"Repository for project '{project_name}' does not exist at path: {git_path}")

    repo = Repo(git_path)

    # Get the remote URL
    remote_url_with_api_key = repo.remotes.origin.url
    remote_url, api_key = parse_github_url(remote_url_with_api_key)

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

def fetch_and_checkout_branch(codehost_url: HttpUrl, destination_path: str, project_name: str, branch_name: str, api_key: Optional[SecretStr] = None):
    full_path = os.path.join(destination_path, "git")

    try:
        # If the repository is not already cloned, clone it first
        if not os.path.exists(full_path):
            logger.info(f"Repository not found at {full_path}, cloning now...")

        # Open the repository
        repo = Repo(full_path)
        logger.info(f"Opened repository at {full_path}")

        # Add the directory as a safe directory
        logger.info(f"Adding {full_path} as a safe directory for Git operations")
        repo.git.config('--global', '--add', 'safe.directory', full_path)

        # Handle authentication for fetching and pulling
        url_str = str(codehost_url)
        if api_key:
            # Construct the authentication URL with the token, as done in clone_repository
            url_parts = url_str.split("://")
            auth_url = f"{url_parts[0]}://{api_key.get_secret_value()}@{url_parts[1]}"

            # Set the authenticated URL for the remote
            repo.remotes.origin.set_url(auth_url)
            logger.debug(f"Auth URL set for fetch and pull: {auth_url}")
        else:
            # Ensure we set the original URL if no API key is provided
            repo.remotes.origin.set_url(url_str)

        # Fetch the latest changes from the remote
        logger.info(f"Fetching latest changes from remote for repository at {full_path}")
        repo.remotes.origin.fetch()

        # Checkout the specified branch
        logger.info(f"Checking out branch '{branch_name}'")
        repo.git.checkout(branch_name)

        # Pull the latest changes for the branch
        logger.info(f"Pulling latest changes for branch '{branch_name}'")
        repo.remotes.origin.pull(branch_name)

        logger.info(f"Checked out and updated to the latest commit on branch {branch_name} in {full_path}")

    except GitCommandError as e:
        logger.error(f"Failed to fetch and checkout branch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch and checkout branch: {str(e)}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
