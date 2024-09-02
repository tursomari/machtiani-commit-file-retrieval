from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List
from lib.vcs.repository_manager import clone_repository
from utils import create_project_directories

app = FastAPI()

# Define your models here or in a separate file (e.g., models.py)
class SearchMode(str, Enum):
    content = "content"
    commit = "commit"
    super = "super"

class EmbeddingModel(str, Enum):
    gpt_4o_mini = "gpt-4o-mini"
    vector_ai_plus = "vector-ai-plus"
    hyper_embed_v2 = "hyper-embed-v2"

class FilePathEntry(BaseModel):
    path: str
    size: int
    created_at: str

class FileSearchResponse(BaseModel):
    embedding_model: EmbeddingModel
    mode: SearchMode
    file_paths: List[FilePathEntry]

class VCSType(str, Enum):
    git = "git"
    # Additional VCS types can be added here in the future, e.g., "svn", "mercurial", etc.

class AddRepositoryRequest(BaseModel):
    codehost_url: HttpUrl
    destination_path: str
    project_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None
    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

@app.post("/add-repository/")
def add_repository(data: AddRepositoryRequest):
    codehost_url = data.codehost_url
    project_name = data.project_name
    vcs_type = data.vcs_type
    api_key = data.api_key

    if vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{vcs_type}' is not supported.")

    # Get from a config in future
    destination_path = "/data/user/repositories"

    # Create necessary directories
    create_project_directories(destination_path, project_name)

    # Clone the repository using the module, into the 'git' directory
    clone_repository(codehost_url, destination_path, project_name, api_key)

    return {
        "message": f"{vcs_type} repository added successfully",
        "full_path": f"{destination_path}/{project_name}/repo/git",
        "api_key_provided": bool(api_key)
    }

@app.get("/file-paths/", response_model=FileSearchResponse)
def get_file_paths(
    prompt: str = Query(..., description="The prompt to search for"),
    mode: SearchMode = Query(..., description="Search mode: content, commit, or super"),
    model: EmbeddingModel = Query(..., description="The embedding model used")
) -> FileSearchResponse:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    mock_file_paths = [
        FilePathEntry(path="/path/to/file1.txt", size=12345, created_at="2024-08-23T12:34:56Z"),
        FilePathEntry(path="/path/to/file2.txt", size=67890, created_at="2024-08-23T12:35:56Z"),
        FilePathEntry(path="/path/to/file3.txt", size=54321, created_at="2024-08-23T12:36:56Z")
    ]

    return FileSearchResponse(
        embedding_model=model,
        mode=mode,
        file_paths=mock_file_paths
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}

