from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List

class SearchMode(str, Enum):
    content = "content"
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
    gpt_4o_mini = "gpt-4o-mini"
    vector_ai_plus = "vector-ai-plus"
    hyper_embed_v2 = "hyper-embed-v2"

class FilePathEntry(BaseModel):
    path: str
    size: int
    created_at: str

class FileSearchResponse(BaseModel):
    oid: str
    similarity: float
    file_paths: List[FilePathEntry]
    embedding_model: EmbeddingModel
    mode: SearchMode

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

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.get_secret_value().strip():
            raise ValueError("API key cannot be empty if provided")
        return v
