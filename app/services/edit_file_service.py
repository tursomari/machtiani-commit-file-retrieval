import asyncio
import logging
from typing import Tuple, List

from pydantic import HttpUrl

from app.utils import retrieve_file_contents
from lib.utils.enums import FilePathEntry
from lib.utils.utilities import url_to_folder_name
from lib.ai.llm_model import LlmModel
from lib.edit.edit import edit_file_async

logging.basicConfig(level=logging.INFO)  # Keep commented if configured elsewhere
logger = logging.getLogger(__name__)

async def edit_file_service(
    project_name: str,
    file_path: str,
    instructions: str,
    llm_model_api_key: str,
    llm_model_base_url: HttpUrl,
    model_name: str,
    ignore_files: List[str] = None
) -> Tuple[str, List[str]]:
    """
    Retrieve file content and edit it based on instructions using LLM.

    Returns:
        updated_content: str
        errors: list of strings
    """
    ignore_files = ignore_files or []
    project_name = url_to_folder_name(project_name)
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    # Retrieve the file content
    file_entry = FilePathEntry(path=file_path)
    try:
        contents_dict = await asyncio.to_thread(
            retrieve_file_contents,
            project_name,
            [file_entry],
            ignore_files
        )
    except Exception as e:
        logger.error(f"Error retrieving file content: {e}")
        raise RuntimeError(f"Failed to retrieve file content: {e}")

    if file_path not in contents_dict:
        raise FileNotFoundError(f"File '{file_path}' not found or not accessible.")

    content = contents_dict[file_path]

    # Instantiate LLM
    llm = LlmModel(
        api_key=llm_model_api_key,
        base_url=str(llm_model_base_url),
        model=model_name
    )

    # Call async edit
    try:
        updated_content, errors = await edit_file_async(llm, content, instructions)
    except Exception as e:
        logger.error(f"Error during file edit: {e}")
        raise RuntimeError(f"Failed to edit file: {e}")

    return updated_content, errors
