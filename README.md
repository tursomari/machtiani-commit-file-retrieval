
# businessmachine-work

Code retrieval and file path search via embeddings.

## Overview

This project aims to provide a two-pronged approach:

1. **Document and Code Retrieval**: A service that allows you to generate summaries of files (e.g., source code) and retrieve the full file by its name.
2. **Commit Message Generation and Indexing**: A service that auto-generates commit messages and indexes them against the hashes of the affected files.

While everything is currently part of this single project, it can be broken up into separate projects if needed.

## Setup

Add .env file.

```
OPENAI_API_KEY=sk-proj...
```

Build.

```
docker-compose build
```

## Local API Service

This project now includes a FastAPI-based local service that serves endpoints for file path retrieval and other related tasks.

### FastAPI Endpoints

1. **File Path Retrieval**: An endpoint to search for file paths based on a given prompt, search mode, and embedding model.
2. **Health Check**: A simple health check endpoint to verify the service status.
3. **Add Repository**: An endpoint to add a repository that can be searched, requiring a code host URL and optionally an API key.

### Running the FastAPI Application

This will start the FastAPI server, and the application will be accessible at `http://localhost:5070`.

```
docker-compose up
```

### Accessing the API Documentation

Once the FastAPI application is running, you can access the automatically generated Swagger UI documentation at:

```
http://localhost:5070/docs
```

You can use this interface to interactively test the endpoints and view their inputs and outputs.

For example, `add_repository`. It will clone the repo to the data. When you restart the service, it will automatically capture the git logs and index.

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
