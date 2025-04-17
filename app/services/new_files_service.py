import asyncio
import logging
import os
from typing import Tuple, List, Dict
from fastapi import HTTPException
from pydantic import HttpUrl

from app.utils import DataDir
from lib.utils.utilities import url_to_folder_name
from lib.ai.llm_model import LlmModel
from lib.edit.edit import find_files_to_create_async, parse_entire_file_update

logger = logging.getLogger(__name__)

# Prompt for generating new file content
new_file_content_prompt = """
We need to create a new file based on the following instructions:

--- BEGIN INSTRUCTIONS ---
{instructions}
--- END INSTRUCTIONS ---

The file to create is: {file_path}

Please generate the entire content for this new file based on the instructions.
Present your answer in this format:

======= ENTIRE_UPDATED_FILE
<the complete file content here>
======= ENTIRE_UPDATED_FILE
"""

async def new_files_service(
    project_name: str,
    instructions: str,
    llm_model_api_key: str,
    llm_model_base_url: HttpUrl,
    model_name: str,
    ignore_files: List[str] = None
) -> Tuple[Dict[str, str], List[str], List[str]]:
    """
    Identify files that need to be created based on instructions and generate content for them.

    Returns:
        new_content: dict mapping file paths to their generated content
        new_file_paths: list of file paths to create
        errors: list of errors encountered
    """
    ignore_files = ignore_files or []
    project_name = url_to_folder_name(project_name)
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    # Instantiate LLM
    llm = LlmModel(
        api_key=llm_model_api_key,
        base_url=str(llm_model_base_url),
        model=model_name
    )

    # Calculate the root directory for the project
    root_dir = os.path.join(DataDir.REPOS, project_name, "git")

    # Find files to create
    try:
        file_paths, find_errors = await find_files_to_create_async(
            llm,
            instructions,
            root_dir=root_dir
        )
    except Exception as e:
        logger.exception("Error in find_files_to_create_async")
        raise HTTPException(500, f"Failed to identify new files: {e}")

    if not file_paths:
        return {}, [], find_errors or ["No files to create were identified."]

    # Generate content for each file
    new_contents = {}
    gen_errors = []

    for file_path in file_paths:
        try:
            # Create a prompt specifically for generating this file's content
            prompt = new_file_content_prompt.format(
                instructions=instructions,
                file_path=file_path
            )

            # Send prompt to LLM
            response = await llm.send_prompt_async(prompt)

            # Parse the response to extract the file content
            content = parse_entire_file_update(response)

            if content is None:
                error_msg = f"Failed to generate valid content for {file_path}"
                logger.error(error_msg)
                gen_errors.append(error_msg)
            else:
                new_contents[file_path] = content
        except Exception as e:
            error_msg = f"Failed to generate content for {file_path}: {str(e)}"
            logger.error(error_msg)
            gen_errors.append(error_msg)

    # Combine all errors
    all_errors = find_errors + gen_errors

    return new_contents, file_paths, all_errors
