import os
import json
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

# Load environment variables from a .env file
load_dotenv()

# Set up your OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Initialize the OpenAIEmbeddings object with the API key
embedding_generator = OpenAIEmbeddings(openai_api_key=openai_api_key, model="text-embedding-3-large")

# Load existing embeddings from embedd.json if it exists
embedd_path = 'commits_embeddings.json'
if os.path.exists(embedd_path):
    with open(embedd_path, 'r') as file:
        existing_embeddings = json.load(file)
else:
    existing_embeddings = {}

# List of commit objects
commits = [
    {
        "oid": "5db7c7d9124f786601136f80ff14882e5845e6de",
        "message": "Add `pyproject.toml` with Poetry configuration and dependencies\n\n- Initialize `pyproject.toml` for the `businessmachine-work` project.\n- Configure Poetry with project metadata, including name, version, description, authors, and license.\n- Specify Python version compatibility (^3.8) and add dependencies for LangChain, OpenAI, and Anthropic.",
        "files": [
            "pyproject.toml"
        ]
    },
    {
        "oid": "dac48836919c38b4749e48d392d1effe63a40fca",
        "message": "Update README: Outline two-pronged approach for code retrieval with summary generation and commit message automation services.",
        "files": [
            "README.md"
        ]
    },
    {
        "oid": "fb59d4c38de94b6ed02e50796cfd8380375ac88d",
        "message": "Update dependencies in pyproject.toml for LangChain integration\n\n- Upgraded `langchain` to version `^0.2.14`\n- Replaced `openai` and `anthropic` with `langchain-openai` and `langchain-anthropic`, respectively, to support latest LangChain features.",
        "files": [
            "pyproject.toml"
        ]
    },
    {
        "oid": "2bec5ab37eae9ba7f1b67169c3bb2a5034d19cae",
        "message": "Add `git_commit_parser.py` script to retrieve and parse commit details\n\n- Implement `get_commit_info` function to extract commit OID, message, and changed files using subprocess and Git commands.\n- Implement `iterate_commits` function to retrieve information for a specified number of commits.\n- Add main execution block to print commit logs in JSON format.\n- Handle errors gracefully with exception handling.",
        "files": [
            "scripts/git_commit_parser.py"
        ]
    }
]

# Filter out commits that already have embeddings
new_commits = [commit for commit in commits if commit['oid'] not in existing_embeddings]

if new_commits:
    # Extract messages from the new commits for embedding
    messages = [commit['message'] for commit in new_commits]

    # Generate embeddings for each new commit message
    embeddings = embedding_generator.embed_documents(messages)

    # Add new embeddings to the existing dictionary
    for commit, embedding in zip(new_commits, embeddings):
        existing_embeddings[commit['oid']] = {
            "message": commit['message'],
            "embedding": embedding
        }

    # Save the updated embeddings dictionary
    with open(embedd_path, 'w') as json_file:
        json.dump(existing_embeddings, json_file, indent=4)

    print(f"Embeddings for {len(new_commits)} new commits saved in '{embedd_path}'")
else:
    print("No new commits to embed.")

