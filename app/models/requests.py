from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List, Dict
from lib.utils.enums import VCSType


class AddRepositoryRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
    ignore_files: List[str] = []  # Default to an empty list
    api_key: Optional[SecretStr] = None
    openai_api_key: Optional[SecretStr] = None

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

    @validator('openai_api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

class LoadRequest(BaseModel):
    openai_api_key: Optional[str]  # Make it optional
    project_name: str
    ignore_files: Optional[List[str]] = None

class DeleteStoreRequest(BaseModel):
    project_name: str
    codehost_url: HttpUrl
    ignore_files: List[str] = []  # Default to an empty list
    vcs_type: VCSType
    api_key: Optional[SecretStr] = None
    openai_api_key: Optional[SecretStr] = None

class DeleteStoreResponse(BaseModel):
    success: bool
    message: str
