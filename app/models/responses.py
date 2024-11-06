from pydantic import BaseModel
from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from lib.utils.enums import VCSType
from typing import Optional, List, Dict

class AddRepositoryResponse(BaseModel):
    message: str
    full_path: str
    api_key_provided: bool
    openai_api_key_provided: bool

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
    branch_name: str
    ignore_files: List[str] = []  # Default to an empty list
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None
    openai_api_key: Optional[SecretStr] = None

    @validator('openai_api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

class FetchAndCheckoutResponse(BaseModel):
    message: str
    branch_name: str
    project_name: str
