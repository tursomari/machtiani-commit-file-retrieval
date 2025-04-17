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
    logger.info(f"Initializing new file service for project: {project_name}")
    ignore_files = ignore_files or []
    project_name = url_to_folder_name(project_name)
    if not project_name.strip():
        logger.error("Empty project name provided")
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    try:
        llm = LlmModel(
            api_key=llm_model_api_key,
            base_url=str(llm_model_base_url),
            model=model_name
        )
        logger.debug(f"LLM Model initialized: {model_name}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM Model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize LLM Model: {e}")

    root_dir = os.path.join(DataDir.REPO.get_path(project_name), "git")
    logger.info(f"Project root directory: {root_dir}")

    try:
        logger.info("Finding files to create...")
        file_paths, find_errors = await find_files_to_create_async(
            llm,
            instructions,
            root_dir=root_dir
        )
        logger.info(f"Identified {len(file_paths)} files to create")
        if find_errors:
            logger.warning(f"Errors during file identification: {find_errors}")
    except Exception as e:
        logger.error(f"Error in find_files_to_create_async: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to identify new files: {e}")

    if not file_paths:
        logger.info("No files to create")
        return {}, [], find_errors or ["No files to create were identified."]

    new_contents = {}
    gen_errors = []

    for file_path in file_paths:
        try:
            logger.info(f"Generating content for {file_path}...")
            prompt = new_file_content_prompt.format(
                instructions=instructions,
                file_path=file_path
            )
            logger.debug(f"Prompt: {prompt[:100]}...")  # Log the first 100 characters of the prompt

            response = await llm.send_prompt_async(prompt)
            logger.debug(f"Received response for {file_path}: {response[:100]}...")  # Log the first 100 characters of the response

            content = parse_entire_file_update(response)
            if content is None:
                error_msg = f"Failed to generate valid content for {file_path}"
                logger.error(error_msg)
                gen_errors.append(error_msg)
            else:
                new_contents[file_path] = content
                logger.info(f"Successfully generated content for {file_path}")
        except Exception as e:
            error_msg = f"Failed to generate content for {file_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            gen_errors.append(error_msg)

    all_errors = find_errors + gen_errors
    logger.info(f"Total errors encountered: {len(all_errors)}")

    return new_contents, file_paths, all_errors
