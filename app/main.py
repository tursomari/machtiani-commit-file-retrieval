import os
from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import ValidationError
from lib.vcs.repo_manager import clone_repository, add_repository, fetch_and_checkout_branch, get_repo_info
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.utils.utilities import read_json_file, write_json_file
from app.utils import DataDir, retrieve_file_contents
from typing import Optional, List, Dict
from lib.utils.enums import (
    SearchMode,
    MatchStrength,
    EmbeddingModel,
    FilePathEntry,
    FileSearchResponse,
    FileContentResponse,
    VCSType,
    AddRepositoryRequest,
    FetchAndCheckoutBranchRequest
)
import logging
# Use the logger instead of print
logger = logging.getLogger("uvicorn")
logger.info("Application is starting up...")

app = FastAPI()

@app.get("/get-project-info/")
async def get_project_info(project: str = Query(..., description="The name of the project")):
    """
    Get project information including the remote URL and the current git branch.
    """
    try:
        result = get_repo_info(project)
        return result
    except Exception as e:
        logger.error(f"Failed to get project info for '{project}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

#@app.on_event("startup")
@app.post("/load/")
async def load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):

    api_key = load_request.get("api_key")
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
        parser = GitCommitParser(commits_logs_json, project)
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
def handle_add_repository(data: AddRepositoryRequest):
    return add_repository(data)

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
    mode: SearchMode = Query(..., description="Search mode: chat, commit, or super"),  # Updated here
    model: EmbeddingModel = Query(..., description="The embedding model used"),
    api_key: str = Query(..., description="The openai api key."),
    match_strength: MatchStrength = Query(MatchStrength.HIGH, description="The strength of the match")
) -> List[FileSearchResponse]:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(embeddings_file=commits_embeddings_file_path, api_key=api_key)
    closest_matches = matcher.find_closest_commits(prompt, match_strength)

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")
    commits_logs_json = read_json_file(commits_logs_file_path)
    parser = GitCommitParser(commits_logs_json, project)

    responses = []
    for match in closest_matches:
        file_paths = parser.get_files_from_commits(match["oid"])
        closest_file_matches: List[FilePathEntry] = [FilePathEntry(path=fp) for fp in file_paths]

        response = FileSearchResponse(
            oid=match["oid"],
            similarity=match["similarity"],
            file_paths=closest_file_matches,
            embedding_model=model.value,
            mode=mode.value,
        )

        if not closest_file_matches:
            logger.info(f"No valid file paths found for commit {match['oid']}.")
            continue  # Skip this response if no valid files

        responses.append(response)

    return responses

@app.post("/retrieve-file-contents/", response_model=FileContentResponse)
def get_file_contents(
    project_name: str = Query(..., description="The name of the project"),
    file_paths: List[FilePathEntry] = Body(..., description="A list of file paths to retrieve content for")
) -> FileContentResponse:
    """
    Retrieve the content of files specified by file paths within a given project.

    :param project_name: The name of the project to search in.
    :param file_paths: A list of FilePathEntry objects representing the files to retrieve content for.
    :return: A dictionary mapping file paths to their contents and a list of successfully retrieved file paths.
    """
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    if not file_paths:
        raise HTTPException(status_code=400, detail="File paths cannot be empty.")

    # Log the incoming file paths for debugging
    logger.info(f"Received file paths: {file_paths}")

    retrieved_file_paths = []
    contents = {}

    try:
        # Explicitly validate each file path entry
        for entry in file_paths:
            logger.info(f"Validating file path entry: {entry.path}")
            # Pydantic validation can be triggered explicitly
            entry = FilePathEntry(**entry.dict())

        # Use the retrieve_file_contents function to get the contents of the specified files
        file_contents = retrieve_file_contents(project_name, file_paths)

        # Collect the successfully retrieved file paths
        for path in file_contents.keys():
            retrieved_file_paths.append(path)

    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")
    except Exception as e:
        logger.error(f"Error retrieving file contents: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving file contents.")

    return FileContentResponse(contents=file_contents, retrieved_file_paths=retrieved_file_paths)

@app.get("/file-paths/", response_model=FileSearchResponse)
def get_file_paths(
    prompt: str = Query(..., description="The prompt to search for"),
    mode: SearchMode = Query(..., description="Search mode: chat, commit, or super"),  # Updated here
    model: EmbeddingModel = Query(..., description="The embedding model used")
) -> FileSearchResponse:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    mock_file_paths = [
        FilePathEntry(path="/path/to/file1.txt"),
        FilePathEntry(path="/path/to/file2.txt"),
        FilePathEntry(path="/path/to/file3.txt")
    ]

    return FileSearchResponse(

        embedding_model=model,
        mode=mode,
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}

