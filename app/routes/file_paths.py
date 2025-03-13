import os
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from app.models.responses import FileSearchResponse
from lib.utils.enums import (
    SearchMode,
    EmbeddingModel,
    FilePathEntry,
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/file-paths/", response_model=FileSearchResponse)
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
