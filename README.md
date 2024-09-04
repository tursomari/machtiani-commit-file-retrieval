
# machtiani-commit-file-retrieval

Code retrieval and file path search via embeddings.

## Overview

This project provides two main services:

1. **Document and Code Retrieval**: Generate summaries of files (e.g., source code) and retrieve the full file by its name using embedding-based search.
2. **Commit Message Generation and Indexing**: Automatically generate commit messages and index them against the hashes of the affected files, enabling advanced search and retrieval capabilities.

While everything is currently part of this single project, it can be split into separate projects if needed.

Build the Docker containers:

```bash
docker-compose build
```

***Use the fetch and checkout branch endpoint to pull latest git changes in the project you added. When you restart the service, it will automatically reindex.***

## Local API Service

The project includes a FastAPI-based service that provides endpoints for various tasks, including file path retrieval, repository management, and health checks.

### FastAPI Endpoints

**Get Project Info**: Retrieve the remote URL and current branch of a specific project.
**Add Repository**: Add a repository that can be searched, requiring a code host URL and optionally an API key. The repository is cloned to a specific directory, and its commits are indexed.
**Fetch and Checkout Branch**: Fetch and check out a specific branch of a repository, with support for authentication using an API key.
**Infer File**: Infer files based on a similarity search using a given prompt, project, search mode, and embedding model.
**Health Check**: Verify the service status with a simple health check endpoint.
**File Path Retrieval**: Search for file paths based on a given prompt, search mode, and embedding model.


### Running the FastAPI Application

Start the FastAPI server:

```bash
docker-compose up
```

The application will be accessible at `http://localhost:5070`.

### Accessing the API Documentation

After starting the FastAPI application, you can access the automatically generated Swagger UI documentation at:

```bash
http://localhost:5070/docs
```

Use this interface to interactively test the endpoints and view their inputs and outputs.

### Repository Management

- The `add-repository` endpoint clones a repository into the appropriate data directory and indexes the commit logs. 
- The `fetch-and-checkout` endpoint allows you to fetch and check out a branch from the repository.

### Strategy

#### Document Retrieval

1. Embed the prompt.
2. Find related files based on matching embeddings.

#### Commit Message Generation and Indexing

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

- [x] Only embed commits that don't exist in `commits_embeddings.json` - `scripts/embed_commits.py`.
- [x] Turn into a full service:
- [x] Implement FastAPI endpoints.
- [x] Pass api key.
- [x] Fetch and checkout list of projects.
- [x] Add list of files to result of find_closest_commits.
- [ ] Add enpoint to retrieve file content from list of files.
- [ ] Save repo settings:
     - default branch: save in /data/users/repositories/<project>/repo/default_git file
     - you get default from clone
     - always use default on fetch and checkout, later can add branch granularity.
