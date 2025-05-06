from pydantic import BaseModel, HttpUrl, SecretStr, validator, Field
from enum import Enum
from typing import Optional, List, Dict
from lib.utils.enums import VCSType

# Default depth for commit history fetching
DEFAULT_DEPTH_LEVEL = 10000

class CountTokenRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None

class AmplificationLevel(str, Enum):
    OFF = "off"
    LOW = "low"
    MID = "mid"
    HIGH = "high"

class AddRepositoryRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
    ignore_files: List[str] = []  # Default to an empty list
    api_key: Optional[SecretStr] = None
    llm_model_api_key: Optional[SecretStr] = None
    llm_model_base_url: HttpUrl
    head: str
    use_mock_llm: Optional[bool] = False
    amplification_level: AmplificationLevel = AmplificationLevel.LOW  # Default to "low"
    depth_level: int = Field(default=DEFAULT_DEPTH_LEVEL, gt=0) # Added depth_level

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

    @validator('llm_model_api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v


class LoadRequest(BaseModel):
    llm_model: Optional[str] = None
    embeddings_model: Optional[str] = None
    embeddings_model_api_key: Optional[str]
    llm_model_api_key: Optional[str]  # Make it optional
    llm_model_base_url: HttpUrl
    project_name: str
    ignore_files: Optional[List[str]] = None
    head: str
    use_mock_llm: Optional[bool] = False
    amplification_level: AmplificationLevel = AmplificationLevel.LOW  # Default to "low"
    depth_level: int = Field(default=DEFAULT_DEPTH_LEVEL, gt=0)
    llm_threads: Optional[int] = None  # Add this field to control LLM concurrency

class DeleteStoreRequest(BaseModel):
    project_name: str
    codehost_url: HttpUrl
    vcs_type: VCSType
    api_key: Optional[SecretStr] = None
    llm_model_api_key: Optional[SecretStr] = None


class FetchAndCheckoutBranchRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    branch_name: Optional[str] = None  # Now optional
    commit_oid: str  # New mandatory parameter
    ignore_files: List[str] = []  # Default to an empty list
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None
    llm_model_api_key: Optional[SecretStr] = None
    llm_model_base_url: HttpUrl
    head: str
    use_mock_llm: Optional[bool] = False
    amplification_level: AmplificationLevel = AmplificationLevel.LOW  # Default to "low"
    depth_level: int = Field(default=DEFAULT_DEPTH_LEVEL, gt=0)
    llm_threads: Optional[int] = None  # Add this field to control LLM concurrency

    @validator('llm_model_api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v
