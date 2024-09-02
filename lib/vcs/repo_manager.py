import os
import subprocess
from typing import Optional
from pydantic import HttpUrl, SecretStr
from fastapi import HTTPException

def clone_repository(codehost_url: HttpUrl, destination_path: str, project_name: str, api_key: Optional[SecretStr] = None):
    """
    Clones the repository from the given codehost_url into the specified destination path and project name.

    :param codehost_url: The URL of the repository to clone.
    :param destination_path: The base path where the repository should be cloned.
    :param project_name: The name of the directory to clone the repository into.
    :param api_key: Optional API key for authentication.
    :raises HTTPException: If the clone operation fails.
    :return: None
    """
    full_path = os.path.join(destination_path, project_name)

    try:
        # Prepare the git clone command
        clone_cmd = ["git", "clone", str(codehost_url), full_path]

        # Set up environment variables if API key is provided
        env = os.environ.copy()
        if api_key:
            env["GIT_ASKPASS"] = "echo"
            env["GIT_CREDENTIALS"] = api_key.get_secret_value()
            env["GIT_TERMINAL_PROMPT"] = "0"

        # Execute the git clone command
        result = subprocess.run(clone_cmd, env=env, check=True, capture_output=True, text=True)
        print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(e.stderr)
        raise HTTPException(status_code=500, detail=f"Failed to clone the repository: {e.stderr}")


