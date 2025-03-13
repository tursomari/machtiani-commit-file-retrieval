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


class VCSType(str, Enum):
    git = "git"
    # Additional VCS types can be added here in the future, e.g., "svn", "mercurial", etc.

