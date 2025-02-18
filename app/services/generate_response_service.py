import os
import asyncio
import logging
from typing import List
from pydantic import ValidationError
from app.utils import retrieve_file_contents
from lib.utils.utilities import url_to_folder_name, read_json_file
from lib.utils.enums import FilePathEntry, FileContentResponse, FileSearchResponse
from lib.vcs.git_commit_parser import GitCommitParser
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.search.file_embedding_matcher import FileEmbeddingMatcher
from app.utils import DataDir

# Set up logging
logging.basicConfig(level=logging.DEBUG)
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


async def infer_file_service(prompt: str, project: str, mode: str, model: str, match_strength: str, api_key: str) -> List[FileSearchResponse]:
    """Service method to infer file matches."""
    responses = []
    project = url_to_folder_name(project)

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    matcher = CommitEmbeddingMatcher(embeddings_file=commits_embeddings_file_path, api_key=api_key)

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    parser = GitCommitParser(commits_logs_json, project)

    closest_commit_matches = await matcher.find_closest_commits(prompt, match_strength, top_n=5)

    files_embeddings_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project), "files_embeddings.json")
    file_matcher = FileEmbeddingMatcher(embeddings_file=files_embeddings_file_path, api_key=api_key)

    closest_file_matches = await file_matcher.find_closest_files(prompt, match_strength)

    loop = asyncio.get_event_loop()

    inferred_commit_files = []  # To hold inferred files from commits
    inferred_file_matches = []    # To hold inferred files from file matches

    for match in closest_commit_matches:
        file_paths = await loop.run_in_executor(None, parser.get_files_from_commits, match["oid"])
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
            inferred_commit_files.extend(closest_file_paths)  # Add to inferred commit files

    for match in closest_file_matches:
        response = FileSearchResponse(
            oid="",  # Assuming file matches do not have an OID
            similarity=match["similarity"],
            file_paths=[FilePathEntry(path=match["path"])],
            embedding_model=model.value,
            mode=mode.value,
        )
        responses.append(response)
        inferred_file_matches.append(FilePathEntry(path=match["path"]))  # Add to inferred file matches

    # Log the inferred files separately
    logger.info("Inferred files from commits: %s", [file.path for file in inferred_commit_files])
    logger.info("Inferred files from file matches: %s", [file.path for file in inferred_file_matches])

    return responses
