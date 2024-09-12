# machtiani-commit-file-retrieval

Code retrieval and file path search via embeddings.

## Overview

This project provides two main services:

1. **Document and Code Retrieval**: Generate summaries of files (e.g., source code) and retrieve the full file by its name using embedding-based search.
2. **Commit Message Generation and Indexing**: Automatically generate commit messages and index them against the hashes of the affected files, enabling advanced search and retrieval capabilities.

## Getting Started

### Accessing the Web Tool

1. **Open the Web Tool**: Navigate to `http://localhost:5072` in your web browser.

### Homepage Actions

From the homepage, you can choose to:

- **Add Repository**: Navigate to add a new repository.
- **Get Repository Info**: Fetch information about an existing repository.
- **Load Projects**: Load projects into the system.

### Detailed Usage Flow

1. **Load Projects (`load.html`)**:
   - Enter your OpenAI API key.
   - Click **Load Projects** to submit. A success/error message will be displayed based on the operation's outcome.

2. **Add Repository (`add-repository.html`)**:
   - Fill in the form with the code host URL, project name, and your OpenAI API key.
   - Submit to add the repository; you'll receive feedback on success or errors.

3. **Get Repository Info (`pull-repo-data-info.html`)**:
   - Select a project to fetch its information.
   - Submit the form to display the project's details on a new page.

4. **Submit Changes**:
   - To fetch and check out a specific branch, fill in the required fields (code host URL, project name, branch name, API key) and submit.
   - You'll be notified of the operation's success or failure.

### Important Note for Handling New Commits

If new commits are pushed to GitHub after you have already added a repository and loaded projects, you must:

- **Get Repository Info Again**: Re-fetch the repository information to get the latest commits and branches.
- **Load Projects Again**: Reload to ensure any new data is integrated into your local system.

### Result Display

After any operation, you'll be redirected to a results page displaying the operation's success or failure. You can return to the homepage for further actions.

## Local API Service

The project includes a FastAPI-based service that provides endpoints for various tasks, including file path retrieval, repository management, and health checks.

### FastAPI Endpoints

- **Get Project Info**: Retrieve the remote URL and current branch of a specific project.
- **Add Repository**: Add a repository for indexing and searching, requiring a code host URL and optionally an API key. The repository is cloned to a specific directory, and its commits are indexed.
- **Fetch and Checkout Branch**: Fetch and check out a specific branch of a repository, with support for authentication using an API key.
- **Infer File**: Infer files based on a similarity search using a given prompt, project, search mode, and embedding model.
- **Health Check**: Verify the service status with a simple health check endpoint.
- **File Path Retrieval**: Search for file paths based on a given prompt, search mode, and embedding model.

### Running the FastAPI Application

1. Create a `.env` file with your OpenAI API key:

   ```
   OPENAI_API_KEY=skj-proj-...
   ```

2. Start the FastAPI server:

   ```bash
   docker-compose up --build
   ```

3. Access the application at `http://localhost:5070` and explore the API documentation at `http://localhost:5070/docs`.

## Conclusion

This web tool simplifies managing Git repositories through a user-friendly interface, utilizing a FastAPI backend for various tasks like loading projects, adding repositories, fetching project information, and checking out branches.

## To-Do List

- [x] Only embed commits that don't exist in `commits_embeddings.json` - `scripts/embed_commits.py`.
- [x] Turn into a full service:
- [x] Implement FastAPI endpoints.
- [x] Pass api key.
- [x] Fetch and checkout list of projects.
- [x] Add list of files to result of find_closest_commits.
- [x] Add enpoint to retrieve file content from list of files.
- [ ] General support for other models, and locally ran.
- [  ] Save repo settings:
     - default branch: save in /data/users/repositories/<project>/repo/default_git file
     - you get default from clone
     - always use default on fetch and checkout, later can add branch granularity.

