import os
import asyncio
import logging
from typing import List
from pydantic import ValidationError, HttpUrl
from app.utils import retrieve_file_contents
from app.models.responses import FileSearchResponse, FileContentResponse
from lib.utils.utilities import url_to_folder_name, read_json_file
from lib.utils.enums import FilePathEntry
from lib.vcs.git_commit_manager import GitCommitManager
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from app.utils import DataDir

# Set up logging
#logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def retrieve_file_contents_service(project_name: str, file_paths: List[FilePathEntry], ignore_files: List[str]) -> FileContentResponse:
    """Service method to retrieve file contents."""
    retrieved_file_paths = []
    contents = {}

    try:
        file_contents = await asyncio.to_thread(retrieve_file_contents, project_name, file_paths, ignore_files)

        for path in file_contents.keys():
            retrieved_file_paths.append(path)

    except ValidationError as e:
        raise ValueError(f"Validation error: {e}")
    except Exception as e:
        raise RuntimeError(f"Error retrieving file contents: {e}")

    return FileContentResponse(contents=file_contents, retrieved_file_paths=retrieved_file_paths)

async def infer_file_service(
    prompt: str,
    project: str,
    mode: str,
    model: str,
    match_strength: str,
    llm_model_api_key: str,
    llm_model_base_url: HttpUrl,
    embeddings_model_api_key: str,
    ignore_files: List[str],
    head: str
) -> List[FileSearchResponse]:
    """Service method to infer file matches."""
    responses = []
    project = url_to_folder_name(project)

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(
        commits_embedding_filepath=commits_embeddings_file_path,
        embeddings_model_api_key=embeddings_model_api_key,
        embedding_model_base_url=llm_model_base_url
    )

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    logger.info("infer_file_service calls GitCommitManager: {head}")
    parser = GitCommitManager(
        commits_logs_json,
        project,
        llm_model_api_key=llm_model_api_key,
        llm_model_base_url=llm_model_base_url,
        embeddings_model_api_key=embeddings_model_api_key,
        head=head,
        llm_model=model,
        ignore_files=ignore_files,
        skip_summaries=True,
    )

    closest_commit_matches = await matcher.find_closest_commits(prompt, match_strength, top_n=5)
    loop = asyncio.get_event_loop()
    inferred_commit_files = []  # To hold inferred files from commits

    for match in closest_commit_matches:
        file_paths = await loop.run_in_executor(None, parser.get_files_from_commits, match["oid"])
        closest_file_paths: List[FilePathEntry] = [FilePathEntry(path=fp) for fp in file_paths]

        response = FileSearchResponse(
            oid=match["oid"],
            similarity=match["similarity"],
            file_paths=closest_file_paths,
            embedding_model=model.value,
            mode=mode.value,
            path_type='commit'
        )

        if closest_file_paths:
            responses.append(response)
            inferred_commit_files.extend(closest_file_paths)

    logger.info("Inferred files from commits: %s", [file.path for file in inferred_commit_files])
    return responses
