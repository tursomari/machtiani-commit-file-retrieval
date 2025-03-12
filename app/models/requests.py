from pydantic import BaseModel, HttpUrl, SecretStr
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

class LoadRequest(BaseModel):
    llm_model: Optional[str] = None
    embeddings_model: Optional[str] = None
    embeddings_model_api_key: Optional[str]
    llm_api_key: Optional[str]  # Make it optional
    project_name: str
    ignore_files: Optional[List[str]] = None

class DeleteStoreRequest(BaseModel):
    project_name: str
    codehost_url: HttpUrl
    ignore_files: List[str] = []  # Default to an empty list
    vcs_type: VCSType
    api_key: Optional[SecretStr] = None
    openai_api_key: Optional[SecretStr] = None
