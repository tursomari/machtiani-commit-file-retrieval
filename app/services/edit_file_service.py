import asyncio
import logging
import os
import subprocess
import tempfile
from typing import Tuple, List

from fastapi import HTTPException
from pydantic import HttpUrl

from app.utils import retrieve_file_contents, DataDir
from lib.utils.enums import FilePathEntry
from lib.utils.utilities import url_to_folder_name
from lib.ai.llm_model import LlmModel
from lib.edit.edit import edit_file_async

logging.basicConfig(level=logging.INFO)
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
        patch_content: str
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
        error_msg = f"File '{file_path}' not found or not accessible."
        logger.error(error_msg)
        return ("", [error_msg])

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

    # --- PATCH GENERATION SECTION ---
    patch_content = ""
    try:
        logger.info("Starting patch generation process...")

        # 1. Strip trailing whitespace from updated content
        cleaned_updated_content = '\n'.join(
            [line.rstrip() for line in updated_content.splitlines()]
        ) + '\n'
        logger.info("Cleaned updated content by stripping trailing whitespace.")

        # 2. Create temporary directory for diff files
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"Created temporary directory at: {tmpdir}")

            orig_path = os.path.join(tmpdir, "orig_file")
            updated_path = os.path.join(tmpdir, "updated_file")

            try:
                original_contents_dict = await asyncio.to_thread(
                    retrieve_file_contents,
                    project_name,
                    [file_entry],
                    ignore_files
                )
            except Exception as e:
                logger.error(f"Error retrieving original file content: {e}")
                raise RuntimeError(f"Failed to retrieve file content: {e}")


            if file_path not in original_contents_dict:
                error_msg = f"File '{file_path}' not found or not accessible."
                logger.error(error_msg)
                return ("", [error_msg])

            original_content = original_contents_dict[file_path]

            # 4. Write original content to temp orig file
            try:
                with open(orig_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                logger.info(f"Wrote original content to temp file: {orig_path}")
            except Exception as e:
                logger.error(f"Error writing original temp file '{orig_path}': {e}")
                raise RuntimeError(f"Failed to write original temp file: {e}")

            # 5. Write updated (cleaned) content to temp updated file
            try:
                with open(updated_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_updated_content)
                logger.info(f"Wrote updated content to temp file: {updated_path}")
            except Exception as e:
                logger.error(f"Error writing updated temp file '{updated_path}': {e}")
                raise RuntimeError(f"Failed to write updated temp file: {e}")

            git_project_path = os.path.join(DataDir.REPO.get_path(project_name), "git")

            # Use GNU diff with labels instead of git diff
            cmd = [
                'diff',
                '--unified=3',
                f'--label=a/{file_path}',
                f'--label=b/{file_path}',
                orig_path,
                updated_path
            ]
            logger.info(f"Running diff command: {' '.join(cmd)}")

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=git_project_path,  # Run in the git project directory
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                logger.info(f"git diff stdout length: {len(proc.stdout)} characters")
                logger.info(f"git diff stderr: {proc.stderr.strip()}")
                if proc.returncode not in (0, 1):  # 0=no diff, 1=diff found
                    logger.error(
                        f"git diff returned unexpected code {proc.returncode}. "
                        f"stderr: {proc.stderr.strip()}"
                    )
                    raise RuntimeError(f"Error generating patch: {proc.stderr.strip()}")
                patch_content = proc.stdout
                logger.info("Patch generation completed successfully.")
            except Exception as e:
                logger.error(f"Exception during git diff execution: {e}")
                raise RuntimeError(f"Failed to generate patch: {e}")

    except Exception as e:
        logger.error(f"Patch creation failed: {e}")
        raise

    return patch_content, errors
