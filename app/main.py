import os
from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List
from lib.vcs.repo_manager import clone_repository
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.utils.utilities import read_json_file, write_json_file
from app.utils import DataDir
import logging

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
    oid: str
    similarity: float
    file_paths: List[FilePathEntry]
    embedding_model: EmbeddingModel
    mode: SearchMode

class VCSType(str, Enum):
    git = "git"
    # Additional VCS types can be added here in the future, e.g., "svn", "mercurial", etc.

class AddRepositoryRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

@app.on_event("startup")
async def startup_event():
    # Use the logger instead of print
    logger = logging.getLogger("uvicorn")
    logger.info("Application is starting up...")

    # List all projects
    projects = DataDir.list_projects()

    # Iterate over each project and call get_path for each directory type
    for project in projects:
        # Should pull latest git changes
        git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
        logger.info(f"{project}'s git repo path: {git_project_path}")

        # Generate new commit logs
        commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
        commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
        logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")
        commits_logs_json = read_json_file(commits_logs_file_path)
        parser = GitCommitParser(commits_logs_json)
        depth = 1000  # Maximum depth or level of commits to retrieve (should get from config).
        parser.add_commits_to_log(git_project_path, depth)  # Add new commits to the beginning of the log
        write_json_file(parser.commits, commits_logs_file_path)  # Write updated logs back to the JSON file

        # Embed commit logs (if any new ones)
        commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
        logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")
        commits_logs_json = read_json_file(commits_logs_file_path)
        existing_commits_embeddings_json = read_json_file(commits_embeddings_file_path)
        generator = CommitEmbeddingGenerator(commits_logs_json, existing_commits_embeddings_json)
        updated_commits_embeddings_json = generator.generate_embeddings()
        write_json_file(updated_commits_embeddings_json, commits_embeddings_file_path)  # Write updated logs back to the JSON file

        #logger.info(f"Directory path for commit embeddings of '{project}': {DataDir.COMMITS_EMBEDDINGS.get_path(project)}")



@app.post("/add-repository/")
def add_repository(data: AddRepositoryRequest):
    codehost_url = data.codehost_url
    project_name = data.project_name
    vcs_type = data.vcs_type
    api_key = data.api_key

    if vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{vcs_type}' is not supported.")

    # Create necessary directories
    DataDir.create_all(project_name)
    destination_path = DataDir.REPO.get_path(project_name)

    # Clone the repository using the module, into the 'git' directory
    clone_repository(codehost_url, destination_path, project_name, api_key)

    return {
        "message": f"{vcs_type} repository added successfully",
        "full_path": f"{destination_path}/{project_name}/repo/git",
        "api_key_provided": bool(api_key)
    }

@app.get("/infer-file/", response_model=FileSearchResponse)
def infer_file(
    prompt: str = Query(..., description="The prompt to search for"),
    project: str = Query(..., description="The project to search"),
    mode: SearchMode = Query(..., description="Search mode: content, commit, or super"),
    model: EmbeddingModel = Query(..., description="The embedding model used")
) -> FileSearchResponse:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(embeddings_file=commits_embeddings_file_path)
    closest_match = matcher.find_closest_commit(prompt)

    # Create an instance of FileSearchResponse with all required fields
    response = FileSearchResponse(
        oid=closest_match["oid"],
        similarity=closest_match["similarity"],
        file_paths=[],  # Replace with the actual file paths if applicable
        embedding_model=model.value,
        mode=mode.value,
    )

    return response

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
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}

