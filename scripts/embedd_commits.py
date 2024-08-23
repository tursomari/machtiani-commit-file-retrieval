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

# Extract messages from the commits for embedding
messages = [commit['message'] for commit in commits]

# Generate embeddings for each commit message
embeddings = embedding_generator.embed_documents(messages)

# Create a dictionary to store the OID and its corresponding embedding
embeddings_dict = {f"commit_{i}": {"oid": commit['oid'], "embedding": embedding}
                   for i, (commit, embedding) in enumerate(zip(commits, embeddings))}

# Save the embeddings in a human-readable JSON format
with open('commits_embeddings.json', 'w') as json_file:
    json.dump(embeddings_dict, json_file, indent=4)

print("Embeddings saved in 'commits_embeddings.json'")

