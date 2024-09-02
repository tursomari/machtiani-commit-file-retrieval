
# businessmachine-work

Code retrieval and file path search via embeddings.

## Overview

This project aims to provide a two-pronged approach:

1. **Document and Code Retrieval**: A service that allows you to generate summaries of files (e.g., source code) and retrieve the full file by its name.
2. **Commit Message Generation and Indexing**: A service that auto-generates commit messages and indexes them against the hashes of the affected files.

While everything is currently part of this single project, it can be broken up into separate projects if needed.

## Example of Document Retrieval Using Embeddings

In this example, `cosine_similarity_match_commits.py` will find the most likely matching commit OID based on an example prompt.

### Setup

Add .env file.

```
OPENAI_API_KEY=sk-proj...
```

Create the `data/commit_logs.json` file:

```bash
poetry run python -m scripts.git_commit_parser_up_to_depth
```

Generate the `commits_embeddings.json` from the project's Git history:

```bash
poetry run python -m scripts.embedd_commits
```

Build the Docker image:

```bash
docker build -t businessmachine-work .
```

### Usage

Find matching commits from `commits_embeddings.json`:

```bash
docker run --rm businessmachine-work scripts.cosine_similarity_match_commits "What is the first commit."
```

## Local API Service

This project now includes a FastAPI-based local service that serves endpoints for file path retrieval and other related tasks.

### FastAPI Endpoints

1. **File Path Retrieval**: An endpoint to search for file paths based on a given prompt, search mode, and embedding model.
2. **Health Check**: A simple health check endpoint to verify the service status.
3. **Add Repository**: An endpoint to add a repository that can be searched, requiring a code host URL and optionally an API key.

### Running the FastAPI Application

To run the FastAPI application locally, use the following command:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5070
```

This will start the FastAPI server, and the application will be accessible at `http://localhost:5070`.

### Accessing the API Documentation

Once the FastAPI application is running, you can access the automatically generated Swagger UI documentation at:

```
http://localhost:5070/docs
```

You can use this interface to interactively test the endpoints and view their inputs and outputs.

### Example FastAPI Endpoint

Here is an outline of what the FastAPI service includes:

```python
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from enum import Enum
from typing import List

class SearchMode(str, Enum):
    content = "content"
    commit = "commit"
    super = "super"

class EmbeddingModel(str, Enum):
    gpt_4o_mini = "gpt-4o-mini"
    vector_ai_plus = "vector-ai-plus"
    hyper_embed_v2 = "hyper-embed-v2"

class FilePathEntry(BaseModel):
    path: str
    size: int  # Size in bytes
    created_at: str  # ISO 8601 formatted timestamp

class FileSearchResponse(BaseModel):
    embedding_model: EmbeddingModel
    mode: SearchMode
    file_paths: List[FilePathEntry]

app = FastAPI()

@app.get("/file-paths/", response_model=FileSearchResponse)
def get_file_paths(
    prompt: str = Query(..., description="The prompt to search for"),
    mode: SearchMode = Query(..., description="Search mode: content, commit, or super"),
    model: EmbeddingModel = Query(..., description="The embedding model used")
) -> FileSearchResponse:
    # Example implementation to be developed
    pass

@app.post("/add-repository/")
def add_repository(data: AddRepositoryRequest):
    # Example logic to add a repository
    pass

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

## Strategy

### Document Retrieval

1. Embed the prompt.
2. Find related files based on matching embeddings.

### Commit Message Generation and Indexing

1. Diff the changes.
2. Generate a concise and informative Git commit message using an AI model.
3. Embed and index all commit messages against the affected files.

### Example Commit Message Indexing Structure

```json
{
  "<commit-message-embedding>": ["<file1>", "<file2>", ...],
  "<commit-message-embedding>": ["<file3>", "<file4>", ...]
}
```

## To-Do List

- [ x ] Only embed commits that don't exist in commits_embeddings.json - `scripts/embedd_commits.py`.
- [ ] Turn into a service
     - docker-compose.yml
     - mount data volume to /data in container
     - git data goes into /data/user/repositories/<project_name>/repo/git
     - commit embeddings go into /data/user/repositories/<project_name>/commits/embeddings/
     - commit logs json go into /data/user/repositories/<project_name>/commits/logs/
     - content embeddings go into /data/user/repositories/<project_name>/contents/embeddings/
     - content logs json go into /data/user/repositories/<project_name>/contents/logs/
     - an endpoint that users can pass git url and api key, if needed.

- [ ] Implement FastAPI endpoints.
