from fastapi import APIRouter, HTTPException, Body
from pydantic import HttpUrl
from typing import List, Dict
import logging


from app.services.new_files_service import new_files_service

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/new-files/")
async def new_files(
    project: str = Body(..., description="Project name"),
    instructions: str = Body(..., description="Instructions for file creation"),
    llm_model_api_key: str = Body(..., description="LLM API key"),
    llm_model_base_url: HttpUrl = Body(..., description="LLM API base URL"),
    model: str = Body("gpt-4", description="LLM model name"),
    ignore_files: List[str] = Body(default_factory=list, description="Ignore files list (optional)")
) -> Dict:
    """
    Call new_files_service to identify and create new files based on instructions.
    """
    if not instructions.strip():
        raise HTTPException(status_code=400, detail="Instructions cannot be empty.")

    try:
        new_content, new_file_paths, errors = await new_files_service(
            project_name=project,
            instructions=instructions,
            llm_model_api_key=llm_model_api_key,
            llm_model_base_url=llm_model_base_url,
            model_name=model,
            ignore_files=ignore_files
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File creation failed: {e}")

    return {
        "new_content": new_content,
        "new_file_paths": new_file_paths,
        "errors": errors
    }
