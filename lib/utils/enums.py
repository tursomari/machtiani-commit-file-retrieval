from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List, Dict

class SearchMode(str, Enum):
    pure_chat = "pure-chat"
    commit = "commit"
    super = "super"

class MatchStrength(Enum):
    HIGH = "high"
    MID = "mid"
    LOW = "low"

    def get_min_similarity(self) -> float:
        if self == MatchStrength.HIGH:
            return 0.40
        elif self == MatchStrength.MID:
            return 0.30
        else:
            return 0.20

class EmbeddingModel(str, Enum):
    gpt_4o = "gpt-4o"
    gpt_4o_mini = "gpt-4o-mini"

class FilePathEntry(BaseModel):
    path: str

class FileSearchResponse(BaseModel):
    oid: str
    similarity: float
    file_paths: List[FilePathEntry]
    embedding_model: EmbeddingModel
    mode: SearchMode

class FileContentResponse(BaseModel):
    contents: Dict[str, str]
    retrieved_file_paths: List[str]

class VCSType(str, Enum):
    git = "git"
    # Additional VCS types can be added here in the future, e.g., "svn", "mercurial", etc.

class AddRepositoryRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
    api_key: Optional[SecretStr] = None

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v

class FetchAndCheckoutBranchRequest(BaseModel):
    codehost_url: HttpUrl
    project_name: str
    branch_name: str
    vcs_type: VCSType = VCSType.git  # Default to "git"
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
