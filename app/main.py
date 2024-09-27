import os
from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import ValidationError
from lib.vcs.repo_manager import clone_repository, add_repository, delete_repository,fetch_and_checkout_branch, get_repo_info
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.utils.utilities import read_json_file, write_json_file, url_to_folder_name
from app.utils import DataDir, retrieve_file_contents, count_tokens
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
async def get_project_info(
    project: str = Query(..., description="The name of the project"),
    api_key: str = Query(..., description="OpenAI API key")
):
    """
    Get project information including the remote URL and the current git branch.
    """
    try:
        result = get_repo_info(project, api_key)
        return result
    except Exception as e:
        logger.error(f"Failed to get project info for '{project}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

#@app.on_event("startup")
@app.post("/load/")
def load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):
    openai_api_key = load_request.get("openai_api_key")  # Change to openai_api_key
    projects = DataDir.list_projects()

    for project in projects:
        git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
        logger.info(f"{project}'s git repo path: {git_project_path}")

        commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
        commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
        logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")
        commits_logs_json = read_json_file(commits_logs_file_path)
        parser = GitCommitParser(commits_logs_json, project)
        depth = 1000
        parser.add_commits_to_log(git_project_path, depth)

        # Create a string by converting this json [] into a string.
        new_commits_string = parser.new_commits

        write_json_file(parser.commits, commits_logs_file_path)

        commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
        logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")
        commits_logs_json = read_json_file(commits_logs_file_path)
        existing_commits_embeddings_json = read_json_file(commits_embeddings_file_path)
        generator = CommitEmbeddingGenerator(commits_logs_json, openai_api_key, existing_commits_embeddings_json)
        updated_commits_embeddings_json = generator.generate_embeddings()
        write_json_file(updated_commits_embeddings_json, commits_embeddings_file_path)

@app.post("/add-repository/")
def handle_add_repository(
    data: AddRepositoryRequest,
):
    openai_api_key = data.openai_api_key

    data.project_name = url_to_folder_name(data.project_name)  # Use the URL to create the folder name

    result_add_repo = add_repository(data)
    openai_api_key = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key}
    token_count = count_tokens_load(load_request)
    logger.info(f"token count: {token_count}")
    logger.info(f"load_request: {load_request}")
    load(load_request)

@app.post("/fetch-and-checkout/")
def handle_fetch_and_checkout_branch(
    data: FetchAndCheckoutBranchRequest,
):
    codehost_url = data.codehost_url
    # data.project_name should be same as codehost_url
    project_name = url_to_folder_name(data.project_name)  # Use the URL to create the folder name
    branch_name = data.branch_name
    api_key = data.api_key
    openai_api_key = data.openai_api_key


    if data.vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{data.vcs_type}' is not supported.")

    # Get the destination path
    destination_path = DataDir.REPO.get_path(project_name)

    logger.info(f"Calling fetching and checkout api_key {api_key}")
    logger.info(f"Calling fetching and checkout api_key type {type(api_key)}")
    # Fetch and checkout the branch using the module function
    fetch_and_checkout_branch(
        codehost_url,
        destination_path,
        project_name,
        branch_name,
        api_key
    )

    openai_api_key = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key}
    count_tokens_load(load_request)
    logger.info(f"load_request: {load_request}")
    load(load_request)

    return {
        "message": f"Fetched and checked out branch '{data.branch_name}' for project '{data.project_name} and updated index.'",
        "branch_name": data.branch_name,
        "project_name": data.project_name
    }

@app.post("/infer-file/", response_model=List[FileSearchResponse])
def infer_file(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: SearchMode = Body(..., description="Search mode: pure-chat, commit, or super"),
    model: EmbeddingModel = Body(..., description="The embedding model used"),
    match_strength: MatchStrength = Body(MatchStrength.HIGH, description="The strength of the match"),
    api_key: str = Body(..., description="OpenAI API key")
) -> List[FileSearchResponse]:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    logger.info(f"project name: {project}")
    project = url_to_folder_name(project)  # Use the URL to create the folder name
    # Load existing commit embeddings from the specified file
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

    project_name = url_to_folder_name(project_name)  # Use the URL to create the folder name
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
    mode: SearchMode = Query(..., description="Search mode: pure-chat, commit, or super"),  # Updated here
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


@app.post("/load/token-count")
def count_tokens_load(
    load_request: dict = Body(..., description="Request body containing text."),
):
    openai_api_key = load_request.get("openai_api_key")  # Change to openai_api_key
    projects = DataDir.list_projects()

    all_new_commits = []  # Initialize an empty list to hold all new commits

    for project in projects:
        git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
        logger.info(f"{project}'s git repo path: {git_project_path}")

        commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
        commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
        logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")
        commits_logs_json = read_json_file(commits_logs_file_path)
        parser = GitCommitParser(commits_logs_json, project)
        depth = 1000
        parser.add_commits_to_log(git_project_path, depth)

        # Create a string by converting this json [] into a string.
        new_commits_string = parser.new_commits

        write_json_file(parser.commits, commits_logs_file_path)

        commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
        logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")
        commits_logs_json = read_json_file(commits_logs_file_path)
        existing_commits_embeddings_json = read_json_file(commits_embeddings_file_path)
        generator = CommitEmbeddingGenerator(commits_logs_json, openai_api_key, existing_commits_embeddings_json)
        new_commits = generator._filter_new_commits()
        logger.info(f"new commits:\n{new_commits}")

        # Append the new commits to the cumulative list
        all_new_commits.extend(new_commits)

    # After the loop exits, convert the aggregated list to a string and calculate tokens
    new_commits_string = str(all_new_commits)
    token_count = count_tokens(new_commits_string)

    # Print or log the final new commits and token count
    logger.info(f"Aggregated new commits across all projects:\n{new_commits_string}")
    logger.info(f"Total token count: {token_count}")

    return {"token_count": token_count}

@app.post("/add-repository/token-count")
def count_tokens_add_repository(
    data: AddRepositoryRequest,
):
    openai_api_key = data.openai_api_key

    data.project_name = url_to_folder_name(data.project_name)  # Use the URL to create the folder name

    result_add_repo = add_repository(data)
    openai_api_key = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key}
    token_count = count_tokens_load(load_request)
    logger.info(f"token count: {token_count}")
    delete_repository(data.project_name)

    return token_count

@app.post("/fetch-and-checkout/token-count")
def count_tokens_fetch_and_checkout(
    data: FetchAndCheckoutBranchRequest,
):
    codehost_url = data.codehost_url
    # data.project_name should be same as codehost_url
    project_name = url_to_folder_name(data.project_name)  # Use the URL to create the folder name
    branch_name = data.branch_name
    api_key = data.api_key
    openai_api_key = data.openai_api_key


    if data.vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{data.vcs_type}' is not supported.")

    # Get the destination path
    destination_path = DataDir.REPO.get_path(project_name)

    logger.info(f"Calling fetching and checkout api_key {api_key}")
    logger.info(f"Calling fetching and checkout api_key type {type(api_key)}")
    # Fetch and checkout the branch using the module function
    fetch_and_checkout_branch(
        codehost_url,
        destination_path,
        project_name,
        branch_name,
        api_key
    )

    openai_api_key = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key}
    token_count = count_tokens_load(load_request)
    logger.info(f"token count: {token_count}")

    return token_count
