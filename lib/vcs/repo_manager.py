from git import Repo, GitCommandError
from pydantic import HttpUrl, SecretStr
from typing import Optional
from fastapi import HTTPException
import os

def clone_repository(codehost_url: HttpUrl, destination_path: str, project_name: str, api_key: Optional[SecretStr] = None):
    full_path = os.path.join(destination_path, "git")

    try:
        # Convert the HttpUrl to a string
        url_str = str(codehost_url)

        if api_key:
            # Construct the authentication URL with the token
            url_parts = url_str.split("://")
            auth_url = f"{url_parts[0]}://{api_key.get_secret_value()}@{url_parts[1]}"

            # Print the URL for debugging (remove this in production)
            print(f"Auth URL: {auth_url}")

            # Clone using the authenticated URL
            Repo.clone_from(auth_url, full_path)
        else:
            Repo.clone_from(url_str, full_path)

        print(f"Repository cloned to {full_path}")

    except GitCommandError as e:
        print(f"Failed to clone the repository: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clone the repository: {str(e)}")

