import os
import asyncio
from typing import List
from concurrent.futures import ProcessPoolExecutor

from lib.vcs.git_commit_parser import GitCommitParser
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.search.file_embedding_matcher import FileEmbeddingMatcher
from lib.utils.utilities import read_json_file, url_to_folder_name
from app.utils import DataDir
from lib.utils.enums import SearchMode, MatchStrength, EmbeddingModel, FilePathEntry, FileSearchResponse

from app.routes.load import handle_load
from fastapi import APIRouter, HTTPException, Body
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

executor = ProcessPoolExecutor(max_workers=10)

@router.post("/infer-file/", response_model=List[FileSearchResponse])
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
