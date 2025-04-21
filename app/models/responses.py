from pydantic import BaseModel
from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from lib.utils.enums import VCSType, FilePathEntry, EmbeddingModel, SearchMode
from typing import Optional, List, Dict

class AddRepositoryResponse(BaseModel):
    message: str
    full_path: str
    api_key_provided: bool
    llm_model_api_key_provided: bool

class TokenCountResponse(BaseModel):
    token_count: int

class ErrorResponse(BaseModel):
    detail: str

class LoadResponse(BaseModel):
    embedding_tokens: int
    inference_tokens: int

class LoadErrorResponse(BaseModel):
    detail: str

class DeleteStoreResponse(BaseModel):
    success: bool
    message: str


class FetchAndCheckoutBranchRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    branch_name: Optional[str] = None  # Now optional
    commit_oid: str  # New mandatory parameter
    ignore_files: List[str] = []  # Default to an empty list
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None
    llm_model_api_key: Optional[SecretStr] = None
    llm_model_base_url: Optional[str] = None
    head: Optional[bool] = None
    use_mock_llm: Optional[bool] = False
    amplification_level: Optional[int] = None
    depth_level: Optional[int] = None

    @validator('llm_model_api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v


class FetchAndCheckoutResponse(BaseModel):
    message: str
    branch_name: Optional[str] = None  # Now optional
    commit_oid: str  # Add the commit_oid field
    project_name: str

class FileSummaryResponse(BaseModel):
    file_path: str
    summary: str  # or any other relevant fields for the summary

class FileSearchResponse(BaseModel):
    oid: str
    similarity: float
    file_paths: List[FilePathEntry]
    embedding_model: EmbeddingModel
    mode: SearchMode
    path_type: str

class FileContentResponse(BaseModel):
    contents: Dict[str, str]
    retrieved_file_paths: List[str]
