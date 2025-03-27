import re
import time
from urllib.parse import urlparse, unquote
import json
import os
import asyncio
import subprocess
import logging
from pydantic import SecretStr, HttpUrl
from fastapi import HTTPException
from typing import Optional, List, Dict, Any
from app.utils import DataDir
import numbers

logger = logging.getLogger(__name__)

def validate_commits_embeddings(embeddings: Dict[str, Dict[str, Any]]) -> None:
    """Validate the structure of embeddings JSON."""
    assert isinstance(embeddings, dict), "embeddings must be a dictionary"
    for commit_oid, data in embeddings.items():
        assert isinstance(commit_oid, str), "Commit OID must be a string"
        assert isinstance(data, dict), "Embedding data must be a dictionary"

        assert "messages" in data, "Embedding must have a 'messages' field"
        assert isinstance(data["messages"], list), "Messages must be a list"
        assert all(isinstance(m, str) for m in data["messages"]), "All messages must be strings"

        assert "embeddings" in data, "Embedding must have an 'embeddings' field"
        assert isinstance(data["embeddings"], list), "Embeddings must be a list" # embeddings is a list now

        for embedding_vector in data["embeddings"]: # Iterate through each embedding vector
            assert isinstance(embedding_vector, list), "Each embedding must be a list (vector)"
            for num in embedding_vector:  # Iterate through numbers in each vector
                assert isinstance(num, numbers.Number), "Embedding values must be numbers"

        # Assert that the length of messages matches the length of embeddings (number of vectors)
        assert len(data["messages"]) == len(data["embeddings"]), \
            "The length of messages must match the number of embedding vectors"

def validate_files_embeddings(embeddings: Dict[str, Dict[str, Any]]) -> None:
    """Validate the structure of files_embeddings."""
    assert isinstance(embeddings, dict), "files_embeddings must be a dictionary"
    for file_path, data in embeddings.items():
        assert isinstance(file_path, str), "File path must be a string"
        assert isinstance(data, dict), "File embedding data must be a dictionary"
        assert "summary" in data, "File embedding must have a 'summary' field"
        assert isinstance(data["summary"], str), "Summary must be a string"
        assert "embedding" in data, "File embedding must have an 'embedding' field"
        assert isinstance(data["embedding"], list), "Embedding must be a list"
        for num in data["embedding"]:
            assert isinstance(num, numbers.Number), "Embedding values must be numbers"

def validate_commits_logs(commits: List[Dict[str, Any]]) -> None:
    """Validate the structure of commits_logs."""
    assert isinstance(commits, list), "commits_logs must be a list"
    for commit in commits:
        assert isinstance(commit, dict), "Each commit must be a dictionary"
        assert "oid" in commit, "Commit must have an 'oid' field"
        assert isinstance(commit["oid"], str), "Commit OID must be a string"
        assert "message" in commit, "Commit must have a 'message' field"
        assert isinstance(commit["message"], list), "Message must be a list"
        assert all(isinstance(m, str) for m in commit["message"]), "All messages must be strings"
        assert "files" in commit, "Commit must have a 'files' field"
        assert isinstance(commit["files"], list), "Files must be a list"
        assert all(isinstance(f, str) for f in commit["files"]), "All files must be strings"
        if "diffs" in commit:
            assert isinstance(commit["diffs"], dict), "Diffs must be a dictionary"
        if "summaries" in commit:
            assert isinstance(commit["summaries"], list), "Summaries must be a list"

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
        logger.info(f"Added safe directory: {git_project_path}")
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
    except IOError as e:
        logger.error(f"Error writing to file {file_path}: {e}")

def validate_auth_url(auth_url: str) -> bool:
    """
    Validate the authentication URL format.

    The expected format is: https://<auth-token>@<domain>/<user>/<project>/
    The trailing slash is optional.

    Parameters:
        auth_url (str): The authentication URL to validate.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    # Regex to validate the auth URL format with any domain
    pattern = r"^https://[a-zA-Z0-9_-]+@[a-zA-Z0-9.-]+/[^/]+/[^/]+/?$"  # Trailing slash is optional
    match = re.match(pattern, auth_url)

    if match:
        return True
    else:
        logger.error(f"Invalid authentication URL")
        return False



def url_to_folder_name(repo_url: str) -> str:
    # Normalize the repository URL by stripping unwanted characters
    repo_url = repo_url.rstrip('/')

    # Remove only the ".git" suffix from the URL if present
    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]

    parsed_url = urlparse(repo_url)

    # Validate scheme (but do not include it in the folder name)
    if parsed_url.scheme not in ['http', 'https', 'git']:
        raise ValueError("Unsupported URL scheme")

    netloc = parsed_url.netloc  # e.g., github.com, localhost:3000
    path = parsed_url.path.strip("/")
    path_components = path.split('/')

    if len(path_components) < 2:
        raise ValueError("Invalid repository URL format")

    user, repo_name = path_components[0], path_components[1]

    # Construct folder name without the scheme
    folder_name = f"{netloc}_{user}_{repo_name}"

    # Replace special characters and lowercase
    folder_name = re.sub(r'[^\w\-]', '_', folder_name).lower()

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
        # Get the raw token value
        key_value = api_key.get_secret_value()

        url_parts = url_str.split("://")
        if len(url_parts) != 2:
            raise ValueError("Invalid codehost URL format.")

        auth_url = f"{url_parts[0]}://{key_value}@{url_parts[1]}"

        if not validate_auth_url(auth_url):
            logger.error(f"Invalid authentication URL")
            raise HTTPException(status_code=400, detail="Invalid Authorized URL format.")

        return auth_url

    logger.debug("Using unauthenticated URL.")
    return url_str


def repo_exists(project_name: str) -> bool:
    """Check if the git repository for the specified project exists."""
    git_project_path = os.path.join(DataDir.REPO.get_path(project_name), "git")
    return os.path.exists(git_project_path)  # Use os.path.exists for synchronous check

