from fastapi import APIRouter, HTTPException, Body
from pydantic import HttpUrl
from typing import List, Dict
import logging

from app.services.edit_file_service import edit_file_service

router = APIRouter()

logging.basicConfig(level=logging.INFO)  # Keep commented if configured elsewhere
logger = logging.getLogger(__name__)

@router.post("/file-edit/")
async def file_edit(
    project: str = Body(..., description="Project name"),
    file_path: str = Body(..., description="Relative file path inside repo"),
    instructions: str = Body(..., description="Edit instructions"),
    llm_model_api_key: str = Body(..., description="LLM API key"),
    llm_model_base_url: HttpUrl = Body(..., description="LLM API base URL"),
    model: str = Body("gpt-4", description="LLM model name"),
    ignore_files: List[str] = Body(default_factory=list, description="Ignore files list (optional)")
) -> Dict:
    """
    Call edit_file_service to edit a file.
    """
    if not instructions.strip():
        raise HTTPException(status_code=400, detail="Instructions cannot be empty.")

    try:
        updated_content, errors = await edit_file_service(
            project_name=project,
            file_path=file_path,
            instructions=instructions,
            llm_model_api_key=llm_model_api_key,
            llm_model_base_url=llm_model_base_url,
            model_name=model,
            ignore_files=ignore_files
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File edit failed: {e}")

    return {
        "updated_content": updated_content,
        "errors": errors
    }
