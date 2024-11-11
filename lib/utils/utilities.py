import re
import time
from urllib.parse import urlparse
import json
import os
import asyncio
import subprocess
import logging
from pydantic import HttpUrl, SecretStr
from typing import Optional
from app.utils import DataDir

logger = logging.getLogger(__name__)

def add_safe_directory(git_project_path):
    try:
        # Get the user's home directory
        home_dir = os.path.expanduser("~")

        # Run the git config command in the user's home directory
        result = subprocess.run(
            ['git', 'config', '--global', '--add', 'safe.directory', git_project_path],
            check=True,
            cwd=home_dir,  # Set the current working directory to the user's home
            stderr=subprocess.PIPE,  # Capture stderr for logging
            stdout=subprocess.PIPE   # Capture stdout for logging (optional)
        )
        logger.info(f"Successfully added safe directory: {git_project_path}")
    except subprocess.CalledProcessError as e:
        # Log the error details
        logger.error(f"Error adding safe directory: {e.stderr.decode().strip()}")
        raise


def read_json_file(file_path):
    """
    Reads a JSON file and returns its content as a Python object.
    If the file doesn't exist or an error occurs, it returns an empty dictionary.
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            logger.info(f"Successfully read data from {file_path}")
            return data
    except FileNotFoundError:
        logger.warning(f"File {file_path} not found. Returning an empty dictionary.")
        return {}  # Change here to return an empty dictionary instead of a list
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return {}  # Also return an empty dictionary on JSON error

def write_json_file(data, file_path):
    """
    Writes a Python object to a JSON file.
    If the file doesn't exist, it creates it.
    """
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=2)
            logger.info(f"Successfully wrote data to {file_path}")
    except IOError as e:
        logger.error(f"Error writing to file {file_path}: {e}")

def parse_github_url(github_url: str):
    # Regex to extract the token and the URL part
    pattern = r"(https://ghp_[a-zA-Z0-9]+)@(github.com/[\w-]+/[\w-]+)"

    match = re.match(pattern, github_url)
    if match:
        token = match.group(1).replace("https://", "")
        url_part = match.group(2)

        # Parse the URL to extract user and repo
        parsed_url = urlparse(f"https://{url_part}")
        user_repo_path = parsed_url.path.strip("/")

        # Return the tuple
        return f"https://{parsed_url.netloc}/{user_repo_path}/", token
    else:
        raise ValueError("Invalid GitHub URL format")

def validate_github_auth_url(github_url: str) -> bool:
    """
    Validate the GitHub URL format.

    The expected format is: https://<github-api-key>@github.com/<user>/<project>/
    The trailing slash is optional.

    Parameters:
        github_url (str): The GitHub URL to validate.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    pattern = r"^https://ghp_[a-zA-Z0-9]+@github\.com/[^/]+/[^/]+/?$"  # Trailing slash is optional
    match = re.match(pattern, github_url)

    if match:
        logger.info(f"Valid GitHub URL: {github_url}")
        return True
    else:
        logger.error(f"Invalid GitHub URL: {github_url}")
        return False

def url_to_folder_name(repo_url: str) -> str:
    # Normalize the repository URL by stripping unwanted characters
    repo_url = repo_url.rstrip('/')

    # Extract the domain, user, and repo name
    match = re.match(r"https?://(www\.)?(github\.com)/([^/]+)/([^/]+)", repo_url)
    if not match:
        raise ValueError("Invalid GitHub URL")

    domain = match.group(2)  # Ensure we only capture 'github.com'
    user = match.group(3)
    repo_name = match.group(4)

    # Remove the ".git" suffix if present in the repository name
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]

    # Combine domain, user, and repo into a folder name
    folder_name = f"{domain}_{user}_{repo_name}"

    # Replace any non-alphanumeric characters (except hyphens and underscores) with underscores
    folder_name = re.sub(r'[^\w\-]', '_', folder_name)

    folder_name = folder_name.lower()

    return folder_name

async def is_locked(lock_file_path: str) -> tuple:
    """Check if the lock file exists and return the creation time if it does."""
    exists = await asyncio.to_thread(os.path.exists, lock_file_path)
    if not exists:
        return (False, None)

    # Get the creation time of the lock file
    creation_time = os.path.getctime(lock_file_path)
    elapsed_time = time.time() - creation_time  # Calculate elapsed time in seconds

    # Check if the elapsed time is greater than 2 hours
    if elapsed_time > 7200:  # 7200 seconds = 2 hours
        return (False, None)

    return (True, elapsed_time)

async def acquire_lock(lock_file_path: str):
    """Acquire a lock by creating the lock file."""
    # Open the lock file to acquire the lock
    await asyncio.to_thread(open, lock_file_path, 'w')

async def release_lock(lock_file_path: str):
    """Release a lock by removing the lock file."""
    if os.path.exists(lock_file_path):
        await asyncio.to_thread(os.remove, lock_file_path)

def get_lock_file_path(project_name: str) -> str:
    """Get the path for the lock file based on the project name."""
    return os.path.join(DataDir.STORE.get_path(project_name), "repo.lock")

def construct_remote_url(codehost_url: HttpUrl, api_key: Optional[SecretStr] = None) -> str:
    """
    Constructs the remote URL, embedding the API key if provided.

    Args:
        codehost_url (HttpUrl): The base URL of the code host.
        api_key (Optional[SecretStr]): The API key for authentication.

    Returns:
        str: The constructed remote URL.
    """
    url_str = str(codehost_url)

    if api_key:
        # Insert the API key into the URL for authentication
        url_parts = url_str.split("://")
        if len(url_parts) != 2:
            raise ValueError("Invalid codehost URL format.")
        auth_url = f"{url_parts[0]}://{api_key.get_secret_value()}@{url_parts[1]}"
        logger.debug("Constructed authenticated URL.")
        if not validate_github_auth_url(auth_url):
            logger.debug(f"{auth_url} is an invalid authorized URL")
            raise HTTPException(status_code=400, detail="Invalid Authorized GitHub URL format.")
        return auth_url

    logger.debug("Using unauthenticated URL.")
    return url_str
