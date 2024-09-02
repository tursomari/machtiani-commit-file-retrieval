from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List

app = FastAPI()

# Define your models here or in a separate file (e.g., models.py)
class SearchMode(str, Enum):
    content = "content"
    commit = "commit"
    super = "super"

class EmbeddingModel(str, Enum):
    gpt_4o_mini = "gpt-4o-mini"
    vector_ai_plus = "vector-ai-plus"
    hyper_embed_v2 = "hyper-embed-v2"

class FilePathEntry(BaseModel):
    path: str
    size: int
    created_at: str

class FileSearchResponse(BaseModel):
    embedding_model: EmbeddingModel
    mode: SearchMode
    file_paths: List[FilePathEntry]

class AddRepositoryRequest(BaseModel):
    codehost_url: HttpUrl
    api_key: Optional[SecretStr] = None

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

# Define your routes here or import them from a routes.py file
@app.post("/add-repository/")
def add_repository(data: AddRepositoryRequest):
    codehost_url = data.codehost_url
    api_key = data.api_key.get_secret_value() if data.api_key else None

    # Example logic to handle adding the repository
    if "github.com" in codehost_url.host and not api_key:
        raise HTTPException(status_code=400, detail="API key is required for GitHub repositories.")

    return {
        "message": "Repository added successfully",
        "codehost_url": codehost_url,
        "api_key_provided": bool(api_key)
    }

@app.get("/file-paths/", response_model=FileSearchResponse)
def get_file_paths(
    prompt: str = Query(..., description="The prompt to search for"),
    mode: SearchMode = Query(..., description="Search mode: content, commit, or super"),
    model: EmbeddingModel = Query(..., description="The embedding model used")
) -> FileSearchResponse:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    mock_file_paths = [
        FilePathEntry(path="/path/to/file1.txt", size=12345, created_at="2024-08-23T12:34:56Z"),
        FilePathEntry(path="/path/to/file2.txt", size=67890, created_at="2024-08-23T12:35:56Z"),
        FilePathEntry(path="/path/to/file3.txt", size=54321, created_at="2024-08-23T12:36:56Z")
    ]

    return FileSearchResponse(
        embedding_model=model,
        mode=mode,
        file_paths=mock_file_paths
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}

