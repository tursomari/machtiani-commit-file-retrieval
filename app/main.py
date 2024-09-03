import os
from fastapi import FastAPI, Query, HTTPException, Body
from lib.vcs.repo_manager import clone_repository, fetch_and_checkout_branch
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.utils.utilities import read_json_file, write_json_file
from app.utils import DataDir
from typing import Optional, List
from lib.utils.enums import (
    SearchMode,
    MatchStrength,
    EmbeddingModel,
    FilePathEntry,
    FileSearchResponse,
    VCSType,
    AddRepositoryRequest,
    FetchAndCheckoutBranchRequest
)
import logging

app = FastAPI()

#@app.on_event("startup")
@app.post("/load/")
async def load(
    api_key: str = Query(..., description="The openai api key."),
):
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
        generator = CommitEmbeddingGenerator(commits_logs_json, api_key, existing_commits_embeddings_json)
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

@app.post("/fetch-and-checkout/")
def handle_fetch_and_checkout_branch(data: FetchAndCheckoutBranchRequest):
    codehost_url = data.codehost_url
    project_name = data.project_name
    branch_name = data.branch_name
    api_key = data.api_key

    if data.vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{data.vcs_type}' is not supported.")

    # Get the destination path
    destination_path = DataDir.REPO.get_path(data.project_name)

    # Fetch and checkout the branch using the module function
    fetch_and_checkout_branch(
        codehost_url,
        destination_path,
        project_name,
        branch_name,
        api_key
    )

    return {
        "message": f"Fetched and checked out branch '{data.branch_name}' for project '{data.project_name}'",
        "branch_name": data.branch_name,
        "project_name": data.project_name
    }

@app.get("/infer-file/", response_model=List[FileSearchResponse])
def infer_file(
    prompt: str = Query(..., description="The prompt to search for"),
    project: str = Query(..., description="The project to search"),
    mode: SearchMode = Query(..., description="Search mode: content, commit, or super"),
    model: EmbeddingModel = Query(..., description="The embedding model used"),
    api_key: str = Query(..., description="The openai api key."),
    match_strength: MatchStrength = Query(MatchStrength.HIGH, description="The strength of the match")
) -> List[FileSearchResponse]:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(embeddings_file=commits_embeddings_file_path, api_key=api_key)
    closest_matches = matcher.find_closest_commits(prompt, match_strength)

    responses = [
        FileSearchResponse(
            oid=match["oid"],
            similarity=match["similarity"],
            file_paths=[],  # Replace with the actual file paths if applicable
            embedding_model=model.value,
            mode=mode.value,
        )
        for match in closest_matches
    ]

    return responses

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

