from pydantic import BaseModel, HttpUrl, SecretStr, validator
from enum import Enum
from typing import Optional, List, Dict

class SearchMode(str, Enum):
    chat = "chat"
    pure_chat = "pure-chat"
    commit = "commit"
    default = "default"
    answer_only = "answer-only"

class MatchStrength(Enum):
    HIGH = "high"
    MID = "mid"
    LOW = "low"

    # The adjusted, normalized scoring takes care of this,
    # So just let anything with a positive score through.
    def get_min_similarity(self) -> float:
        if self == MatchStrength.HIGH:
            return 0.01
        elif self == MatchStrength.MID:
            return 0.01
        else:
            return 0.01

class EmbeddingModel(str, Enum):
    gpt_4o = "gpt-4o"
    gpt_4o_mini = "gpt-4o-mini"

class FilePathEntry(BaseModel):
    path: str


class VCSType(str, Enum):
    git = "git"
    # Additional VCS types can be added here in the future, e.g., "svn", "mercurial", etc.

