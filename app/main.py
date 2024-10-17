import os
from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import ValidationError, SecretStr, HttpUrl
import asyncio
from concurrent.futures import ProcessPoolExecutor
from lib.vcs.repo_manager import (
    clone_repository,
    add_repository,
    delete_repository,
    fetch_and_checkout_branch,
    get_repo_info_async,
    delete_store,
    check_pull_access,
    check_push_access,
    check_lock_file_exists
)
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.indexer.file_summary_indexer import FileSummaryEmbeddingGenerator
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.search.file_embedding_matcher import FileEmbeddingMatcher
from lib.utils.utilities import (
    read_json_file,
    write_json_file,
    url_to_folder_name,
    get_lock_file_path,
    is_locked,
    acquire_lock,
    release_lock
)
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
    FetchAndCheckoutBranchRequest,
    DeleteStoreRequest
)
import logging

# Use the logger instead of print
logger = logging.getLogger("uvicorn")
logger.info("Application is starting up...")

app = FastAPI()
executor = ProcessPoolExecutor(max_workers=10)

async def fetch_summary(file_path: str, file_summaries: Dict[str, dict]) -> Optional[Dict[str, str]]:
    summary = file_summaries.get(file_path)
    if summary is None:
        logger.warning(f"No summary found for file path: {file_path}")
        return None
    return {"file_path": file_path, "summary": summary["summary"]}


@app.post("/test-pull-access/")
async def test_pull_access(
    project_name: str = Query(..., description="The name of the project"),
    codehost_api_key: SecretStr = Query(..., description="Code host API key for authentication"),
    codehost_url: str = Query(..., description="Code host URL for the repository"),  # New parameter

):
    """ Test pull access by checking if the user can pull from the repository. """
    try:
        _project_name = url_to_folder_name(project_name)
        destination_path = DataDir.REPO.get_path(_project_name)

        # Check pull access
        has_pull_access = await asyncio.to_thread(check_pull_access, codehost_url, destination_path, project_name, codehost_api_key)

        return {"pull_access": has_pull_access}
    except Exception as e:
        logger.error(f"Failed to check pull access for '{project_name}': {e}")
        return {"pull_access": False}

@app.get("/get-project-info/")
async def get_project_info(
    project: str = Query(..., description="The name of the project"),
    api_key: str = Query(..., description="OpenAI API key")
):
    """ Get project information including the remote URL and the current git branch. """
    try:
        result = await get_repo_info_async(project, api_key)
        return result
    except Exception as e:
        logger.error(f"Failed to get project info for '{project}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def check_repo_lock(
    codehost_url: HttpUrl = Query(..., description="Code host URL for the repository"),
    api_key: Optional[SecretStr] = Query(None, description="Optional API key for authentication")
):
    """ Check if the repo.lock file is present after verifying push access. """
    project_name = url_to_folder_name(str(codehost_url))  # Use the URL to create the folder name

    repo_info = await get_repo_info_async(str(codehost_url))
    logger.info(f"check_repo_lock get repo info: {repo_info}")
    # Check for push access
    has_push_access = await asyncio.to_thread(check_push_access, codehost_url, DataDir.REPO.get_path(project_name), project_name, repo_info['current_branch'], api_key)

    if not has_push_access:
        raise HTTPException(status_code=403, detail="User does not have push access to the repository.")

    # Check if the repo.lock file exists
    lock_file_exists = await check_lock_file_exists(codehost_url)

    return {"lock_file_present": lock_file_exists}

@app.get("/get-file-summary/")
async def get_file_summary(
    file_paths: List[str] = Query(..., description="List of file paths to retrieve summaries for"),
    project_name: str = Query(..., description="The name of the project")
):
    """ Retrieve summaries for specified file paths. """
    project_name = url_to_folder_name(project_name)
    file_summaries_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project_name), "files_embeddings.json")

    # Read the existing file summaries asynchronously
    file_summaries = await asyncio.to_thread(read_json_file, file_summaries_file_path)

    # Create a list of async tasks for fetching summaries
    tasks = [fetch_summary(file_path, file_summaries) for file_path in file_paths]
    results = await asyncio.gather(*tasks)

    # Prepare the output, filtering out None results
    summaries = [result for result in results if result is not None]

    if len(summaries) < len(file_paths):
        missing_files = [file_path for file_path, result in zip(file_paths, results) if result is None]
        for file_path in missing_files:
            logger.warning(f"No summary found for file path: {file_path}")

    return summaries

@app.post("/load/")
async def load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):
    openai_api_key = load_request.get("openai_api_key")
    project = load_request.get("project_name")
    ignore_files = load_request.get("ignore_files")

    git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
    logger.info(f"{project}'s git repo path: {git_project_path}")

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")

    async def read_commits_logs():
        return await asyncio.to_thread(read_json_file, commits_logs_file_path)

    commits_logs_json = await read_commits_logs()

    parser = GitCommitParser(commits_logs_json, project)
    depth = 1000
    logger.info("Adding commits to log...")
    await parser.add_commits_to_log(git_project_path, depth)
    logger.info("Finished adding commits to log.")

    new_commits_string = parser.new_commits

    # Log the contents of parser.commits to verify new commits are added
    logger.info(f"New commits added: {parser.commits}")

    await asyncio.to_thread(write_json_file, parser.commits, commits_logs_file_path)

    new_commits_string = parser.new_commits

    await asyncio.to_thread(write_json_file, parser.commits, commits_logs_file_path)

    # Generate Commit Embeddings
    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")

    commits_logs_json = await read_commits_logs()
    existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path)

    generator = CommitEmbeddingGenerator(commits_logs_json, openai_api_key, existing_commits_embeddings_json)
    updated_commits_embeddings_json = await asyncio.to_thread(generator.generate_embeddings)
    await asyncio.to_thread(write_json_file, updated_commits_embeddings_json, commits_embeddings_file_path)

    # Generate File Summaries and Embeddings
    files_embeddings_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project), "files_embeddings.json")
    logger.info(f"{project}'s embedded files logs file path: {files_embeddings_file_path}")

    existing_files_embeddings_json = await asyncio.to_thread(read_json_file, files_embeddings_file_path)

    file_summary_generator = FileSummaryEmbeddingGenerator(commits_logs_json, openai_api_key, git_project_path, ignore_files, existing_files_embeddings_json)

    updated_files_embeddings_json = await asyncio.to_thread(file_summary_generator.generate_embeddings)
    await asyncio.to_thread(write_json_file, updated_files_embeddings_json, files_embeddings_file_path)

@app.post("/add-repository")
@app.post("/add-repository/")
async def handle_add_repository(data: AddRepositoryRequest):
    # Normalize the project name
    data.project_name = url_to_folder_name(data.project_name)

    # Obtain the OpenAI API key value
    openai_api_key_value = data.openai_api_key.get_secret_value() if data.openai_api_key else None

    # Add the repository and retrieve the response
    response = await asyncio.to_thread(add_repository, data)

    # Prepare the load request
    load_request = {
        "openai_api_key": openai_api_key_value,
        "project_name": data.project_name,
        "ignore_files": data.ignore_files
    }

    await load(load_request)  # Await async method

    return {
        "message": response["message"],
        "full_path": response["full_path"],
        "api_key_provided": response["api_key_provided"],
        "openai_api_key_provided": response["openai_api_key_provided"]
    }

@app.post("/fetch-and-checkout")
@app.post("/fetch-and-checkout/")
async def handle_fetch_and_checkout_branch(data: FetchAndCheckoutBranchRequest):
    project_name = url_to_folder_name(data.project_name)  # Normalize the project name
    branch_name = data.branch_name
    lock_file_path = get_lock_file_path(project_name)

    # Check if the operation is locked
    if await is_locked(lock_file_path):
        raise HTTPException(status_code=423, detail=f"Operation is locked for project '{project_name}'. Please try again later.")

    await acquire_lock(lock_file_path)

    try:
        # Call the repository manager to fetch and checkout the branch
        await asyncio.to_thread(
            fetch_and_checkout_branch,
            data.codehost_url,
            DataDir.REPO.get_path(project_name),
            project_name,
            branch_name,
            data.api_key
        )

        # Prepare the load request for counting tokens
        load_request = {
            "openai_api_key": data.openai_api_key.get_secret_value() if data.openai_api_key else None,
            "project_name": project_name,
            "ignore_files": data.ignore_files
        }

        # Calling the load function to generate embeddings
        await load(load_request)

        return {
            "message": f"Fetched and checked out branch '{data.branch_name}' for project '{data.project_name}' and updated index.",
            "branch_name": data.branch_name,
            "project_name": data.project_name,
        }
    finally:
        await release_lock(lock_file_path)

@app.post("/infer-file/", response_model=List[FileSearchResponse])
async def infer_file(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: SearchMode = Body(..., description="Search mode: pure-chat, commit, or super"),
    model: EmbeddingModel = Body(..., description="The embedding model used"),
    match_strength: MatchStrength = Body(..., description="The strength of the match"),
    api_key: str = Body(..., description="OpenAI API key")
) -> List[FileSearchResponse]:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    logger.info(f"project name: {project}")
    project = url_to_folder_name(project)

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(embeddings_file=commits_embeddings_file_path, api_key=api_key)

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    parser = GitCommitParser(commits_logs_json, project)

    # Call the async method
    closest_commit_matches = await matcher.find_closest_commits(prompt, match_strength)

    files_embeddings_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project), "files_embeddings.json")
    file_matcher = FileEmbeddingMatcher(embeddings_file=files_embeddings_file_path, api_key=api_key)

    # Call the async method
    closest_file_matches = await file_matcher.find_closest_files(prompt, match_strength)

    responses = []

    loop = asyncio.get_event_loop()

    # Process fetching file paths for commit matches
    for match in closest_commit_matches:
        file_paths = await loop.run_in_executor(executor, parser.get_files_from_commits, match["oid"])  # Use executor
        closest_file_paths: List[FilePathEntry] = [FilePathEntry(path=fp) for fp in file_paths]

        response = FileSearchResponse(
            oid=match["oid"],
            similarity=match["similarity"],
            file_paths=closest_file_paths,
            embedding_model=model.value,
            mode=mode.value,
        )

        if closest_file_paths:
            responses.append(response)
        else:
            logger.info(f"No valid file paths found for commit {match['oid']}. Skipping this response.")

    for match in closest_file_matches:
        response = FileSearchResponse(
            oid="",  # Assuming file matches do not have an OID
            similarity=match["similarity"],
            file_paths=[FilePathEntry(path=match["path"])],
            embedding_model=model.value,
            mode=mode.value,
        )
        responses.append(response)

    return responses

@app.post("/retrieve-file-contents/", response_model=FileContentResponse)
async def get_file_contents(
    project_name: str = Query(..., description="The name of the project"),
    file_paths: List[FilePathEntry] = Body(..., description="A list of file paths to retrieve content for")
) -> FileContentResponse:
    """ Retrieve the content of files specified by file paths within a given project. """
    project_name = url_to_folder_name(project_name)
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    if not file_paths:
        raise HTTPException(status_code=400, detail="File paths cannot be empty.")

    logger.info(f"Received file paths: {file_paths}")

    retrieved_file_paths = []
    contents = {}

    try:
        for entry in file_paths:
            logger.info(f"Validating file path entry: {entry.path}")
            entry = FilePathEntry(**entry.dict())

        file_contents = await asyncio.to_thread(retrieve_file_contents, project_name, file_paths)

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
async def get_file_paths(
    prompt: str = Query(..., description="The prompt to search for"),
    mode: SearchMode = Query(..., description="Search mode: pure-chat, commit, or super"),
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
async def health_check():
    return {"status": "healthy"}

@app.post("/load/token-count")
async def count_tokens_load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):
    openai_api_key = load_request.get("openai_api_key")
    project = load_request.get("project_name")
    projects = DataDir.list_projects()

    all_new_commits = []

    git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
    logger.info(f"{project}'s git repo path: {git_project_path}")

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    parser = GitCommitParser(commits_logs_json, project)

    depth = 1000
    #await asyncio.to_thread(parser.add_commits_to_log, git_project_path, depth)
    await parser.add_commits_to_log(git_project_path, depth)

    new_commits_string = parser.new_commits

    await asyncio.to_thread(write_json_file, parser.commits, commits_logs_file_path)

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path)
    generator = CommitEmbeddingGenerator(commits_logs_json, openai_api_key, existing_commits_embeddings_json)

    new_commits = await asyncio.to_thread(generator._filter_new_commits)
    logger.info(f"new commits:\n{new_commits}")

    # Ensure you have the correct new commits to count tokens
    if not new_commits:
        logger.info("No new commits to count tokens for.")
        return {"token_count": 0}

    new_commits_messages = [commit['message'] for commit in new_commits]
    new_commits_string = '\n'.join(new_commits_messages)  # Create a string from messages
    token_count = count_tokens(new_commits_string)

    logger.info(f"Aggregated new commits across all projects:\n{new_commits_string}")
    logger.info(f"Total token count: {token_count}")

    return {"token_count": token_count}

@app.post("/add-repository/token-count")
async def count_tokens_add_repository(
    data: AddRepositoryRequest,
):
    openai_api_key = data.openai_api_key

    # Normalize the project name
    data.project_name = url_to_folder_name(data.project_name)

    # Add the repository
    result_add_repo = await asyncio.to_thread(add_repository, data)

    # Extract the OpenAI API key value
    openai_api_key_value = openai_api_key.get_secret_value() if openai_api_key else None

    # Prepare the load request for counting tokens
    load_request = {
        "openai_api_key": openai_api_key_value,
        "project_name": data.project_name,
        "ignore_files": data.ignore_files
    }

    # Count tokens
    token_count = await count_tokens_load(load_request)
    logger.info(f"Token count: {token_count}")

    # Call delete_store with the necessary parameters
    # Correctly call the synchronous function within asyncio.to_thread
    await asyncio.to_thread(
        delete_store,
        codehost_url=data.codehost_url,
        project_name=data.project_name,
        ignore_files=data.ignore_files,
        vcs_type=data.vcs_type,
        api_key=data.api_key,
        openai_api_key=openai_api_key,
    )

    # count_tokens_load `return {"token_count": token_count}` already.
    return token_count

@app.post("/fetch-and-checkout/token-count")
async def count_tokens_fetch_and_checkout(
    data: FetchAndCheckoutBranchRequest,
):
    codehost_url = data.codehost_url
    project_name = url_to_folder_name(data.project_name)
    branch_name = data.branch_name
    api_key = data.api_key
    openai_api_key = data.openai_api_key

    if data.vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{data.vcs_type}' is not supported.")

    destination_path = DataDir.REPO.get_path(project_name)

    logger.info(f"Calling fetching and checkout api_key {api_key}")
    await asyncio.to_thread(fetch_and_checkout_branch, codehost_url, destination_path, project_name, branch_name, api_key)

    openai_api_key = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key, "project_name": project_name, "ignore_files": data.ignore_files}
    token_count = await count_tokens_load(load_request)  # Await async method


    # count_tokens_load `return {"token_count": token_count}` already.
    return token_count

@app.post("/generate-response/token-count")
async def count_tokens_generate_response(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: str = Body(..., description="Search mode: chat, commit, or super"),
    model: str = Body(..., description="The embedding model used"),
    match_strength: str = Body(..., description="The strength of the match"),
):
    """ Count tokens for a given prompt to be used in generating a response. """
    token_count = count_tokens(prompt)

    logger.info(f"Token count for prompt: {token_count}")

    return {"token_count": token_count}

@app.post("/delete-store/")
async def handle_delete_store(
    data: DeleteStoreRequest,
):
    try:
        await asyncio.to_thread(
            delete_store,
            codehost_url=data.codehost_url,
            project_name=data.project_name,
            ignore_files=data.ignore_files,
            vcs_type=data.vcs_type,
            api_key=data.api_key,
            openai_api_key=data.openai_api_key,
        )
        return {"message": f"Store '{data.project_name}' deleted successfully."}
    except ValueError as e:
        logger.error(f"Failed to delete store '{data.project_name}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete store '{data.project_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
def shutdown():
    """ Shutdown the executor when the application terminates. """
    logger.info("Shutting down the executor.")
    executor.shutdown(wait=True)
