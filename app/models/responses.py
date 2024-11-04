from pydantic import BaseModel
from typing import Optional

class AddRepositoryResponse(BaseModel):
    message: str
    full_path: str
    api_key_provided: bool
    openai_api_key_provided: bool

class TokenCountResponse(BaseModel):
    token_count: int

class ErrorResponse(BaseModel):
    detail: str
