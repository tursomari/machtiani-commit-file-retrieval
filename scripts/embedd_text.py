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

# Array of strings to create embeddings for
texts = [
    "Add `pyproject.toml` with Poetry configuration and dependencies\n\n- Initialize `pyproject.toml` for the `businessmachine-work` project.\n- Configure Poetry with project metadata, including name, version, description, authors, and license.\n- Specify Python version compatibility (^3.8) and add dependencies for LangChain, OpenAI, and Anthropic.",
    "Update README: Outline two-pronged approach for code retrieval with summary generation and commit message automation services.",
    "Update dependencies in pyproject.toml for LangChain integration\n\n- Upgraded `langchain` to version `^0.2.14`\n- Replaced `openai` and `anthropic` with `langchain-openai` and `langchain-anthropic`, respectively, to support latest LangChain features.",
    "Add `git_commit_parser.py` script to retrieve and parse commit details\n\n- Implement `get_commit_info` function to extract commit OID, message, and changed files using subprocess and Git commands.\n- Implement `iterate_commits` function to retrieve information for a specified number of commits.\n- Add main execution block to print commit logs in JSON format.\n- Handle errors gracefully with exception handling."
]

# Generate embeddings for each string using embed_documents
embeddings = embedding_generator.embed_documents(texts)

# Create a dictionary to store the original text and its corresponding embedding
embeddings_dict = {f"text_{i}": {"original_text": text, "embedding": embedding}
                   for i, (text, embedding) in enumerate(zip(texts, embeddings))}# Save the embeddings in a human-readable JSON format
with open('embeddings.json', 'w') as json_file:
    json.dump(embeddings_dict, json_file, indent=4)

print("Embeddings saved in 'embeddings.json'")

