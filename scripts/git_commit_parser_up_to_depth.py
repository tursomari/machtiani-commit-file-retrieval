import json
import logging
from lib.vcs.git_commit_parser import GitCommitParser

logging.basicConfig(level=logging.INFO)
# Example usage:
#sample_json = []
sample_json = [
  {
    "oid": "5a13af176931697ac9e7b2027818bb33b66577c4",
    "message": "Update embedd_commits.py to handle new commit embeddings\n\n- Load existing embeddings from 'commits_embeddings.json'\n- Filter out commits that are already embedded\n- Generate embeddings only for new commits\n- Merge new embeddings into the existing dictionary\n- Save the updated embeddings to the JSON file",
    "files": [
      "scripts/embedd_commits.py"
    ]
  },
  {
    "oid": "1a9e6ad8a34f47143b9f3bc9f5fb48c9832b696d",
    "message": "Update README: Add to-do section for commit embedding\n\n- Change \"Scripts and experiments\" section to \"To do\"\n- Add new bullet point to embed only new commits in `embedd.json`",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "6598697c02637adbda51a7b9e0d1e5e9a78392ee",
    "message": "Update `README.md` to reflect changes in script names and example setup. Replaced references to `embeddings.json` with `commits_embeddings.json` and updated usage instructions to use the correct script `cosine_similarity_match_commits.py`. Clarified document retrieval example using embeddings.",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "e4751f4fa5b93e853ee6aa44fa13c33b7ee82757",
    "message": "Add script for cosine similary match for commits.",
    "files": [
      "scripts/cosine_similarity_match_commits.py"
    ]
  },
  {
    "oid": "5680f9159a58b3dac2750223701b83e53058bb6e",
    "message": "Update Dockefile so that it can run any script, but defaults to running cosine similarity match.",
    "files": [
      "Dockerfile"
    ]
  },
  {
    "oid": "88bdef429484f0521b9c7445aecaf8a49320b717",
    "message": "Add script to generate embeddings for commits.",
    "files": [
      "scripts/embedd_commits.py"
    ]
  },
  {
    "oid": "97a8244422387d38c07ddbd84c50a4fe0460b5d2",
    "message": "Git commit parser script stops gracefully when reaching traversing to the last commit level.",
    "files": [
      "scripts/git_commit_parser.py"
    ]
  },
  {
    "oid": "f983a308812d28d57b5b89ef95b9e2cc2430d9fe",
    "message": "Add instruction in README.md on how to setup and use latest scripts example to generate embeddings and find matching text.",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "514930114b80d8438b9d0e5eefa26b63922ab462",
    "message": "Increase commit depth limit in git commit parser to 1000.",
    "files": [
      "scripts/git_commit_parser.py"
    ]
  },
  {
    "oid": "a93dd52e75d3bee278e909fa0a81e9406b02169e",
    "message": "Update poetry.lock by copying latest one inside the working container.",
    "files": [
      "poetry.lock"
    ]
  },
  {
    "oid": "934afc8df6d88678f239466dd911d98f19e075b2",
    "message": "Add Dockerfile to run cosine similary match script.\n\nnumpy required system package installs, so it's better to manage all that in a container.",
    "files": [
      "Dockerfile"
    ]
  },
  {
    "oid": "11cc35b078838293884a6ec40b22a290ae5fc002",
    "message": "Update cosine similarity script to use same embedding openai model 'text-embedding-3-large' as in the script that generated embeddings.json.",
    "files": [
      "scripts/cosine_similarity_match.py"
    ]
  },
  {
    "oid": "300b2e8428df36ebb22002b4adf2819525215109",
    "message": "Update pyproject for numpy 1.26 and python 3.9 to 4.0 that is compatible with other packages.",
    "files": [
      "pyproject.toml"
    ]
  },
  {
    "oid": "86f05b8f86f33fc8ea0b492b56584d1a230c7608",
    "message": "Add cosine similarity match script, to find matching text.",
    "files": [
      "scripts/cosine_similarity_match.py"
    ]
  },
  {
    "oid": "eb98026d5c9d4e2be0d900db76623c1e311f7b39",
    "message": "Add script to embedd an array of text and save in embeddings.json.",
    "files": [
      "scripts/embedd_text.py"
    ]
  },
  {
    "oid": "2bec5ab37eae9ba7f1b67169c3bb2a5034d19cae",
    "message": "Add `git_commit_parser.py` script to retrieve and parse commit details\n\n- Implement `get_commit_info` function to extract commit OID, message, and changed files using subprocess and Git commands.\n- Implement `iterate_commits` function to retrieve information for a specified number of commits.\n- Add main execution block to print commit logs in JSON format.\n- Handle errors gracefully with exception handling.",
    "files": [
      "scripts/git_commit_parser.py"
    ]
  },
  {
    "oid": "b442c9b6de4ee923481b5085806917b312e6245c",
    "message": "Add init files for hypotethical directories for structuring library.\n\n- ai dir: for chat LLM chat and embeddings, etc.\n\n- vcs dir: all things related to managing vcs commits.\n\n- indexer lib: manage store of embeddings, etc, of commit messages and other text.",
    "files": [
      "lib/__init__.py",
      "lib/ai/__init__.py",
      "lib/indexer/__init__.py",
      "lib/vcs/__init__.py"
    ]
  },
  {
    "oid": "8ed1682ffaa5c57d5a850485fd0c9ddd8d2cd7f4",
    "message": "Update README because of name change of langchain usage script.",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "d405fdf074ca2d4addd36c76af01ddf2806b4869",
    "message": "Change langchain usage script name casing to snake case (python file naming convention).",
    "files": [
      "scripts/langchain_usage.py"
    ]
  },
  {
    "oid": "8770a20cea7d1a95833df6868a98246eba164459",
    "message": "Update langchain-usage.py for use with gpt-4o-mini model.",
    "files": [
      "scripts/langchain-usage.py"
    ]
  },
  {
    "oid": "9a5747cf83eb5d5e8dcd37fe4e6e6ec956651150",
    "message": "Rename script demonstrating OpenAI and Anthtropic usage with LangChain to langchain-usage.py.",
    "files": [
      "scripts/langchain-usage.py"
    ]
  },
  {
    "oid": "dd7367d293ef3af35efa71152711f806c07e491d",
    "message": "Add setup instructions and example script for querying with OpenAI and Anthropic using LangChain to README.md",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "2f05381c0a96cc99c18579e6bc55e07303755284",
    "message": "Add initial script to query OpenAI and Anthropic for text translation\n\n- Introduced `hello-query.py` script to demonstrate querying OpenAI and Anthropic LLMs.\n- Loaded API keys from environment variables using dotenv.\n- Created a prompt template for translating text to French.\n- Initialized OpenAI LLM and set up a chain to process the input text.\n- Anthropic LLM initialization and query execution are commented out for now.",
    "files": [
      "scripts/hello-query.py"
    ]
  },
  {
    "oid": "ba8bfc8e8c3e078da1b6964285b03f3dad8ebe60",
    "message": "Add `poetry.lock` to version control to lock dependencies for consistent builds.",
    "files": [
      "poetry.lock"
    ]
  },
  {
    "oid": "01babb8c16fb9a4a64a39007665528eb31839df1",
    "message": "Update Python version in `pyproject.toml` to >=3.8.1 for compatibility with langchain-anthropic.",
    "files": [
      "pyproject.toml"
    ]
  },
  {
    "oid": "1ba4de694de779ea7a5975f39de01d15e0cee3ae",
    "message": "Add `python-dotenv` dependency to `pyproject.toml` for environment variable management.",
    "files": [
      "pyproject.toml"
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
    "oid": "dac48836919c38b4749e48d392d1effe63a40fca",
    "message": "Update README: Outline two-pronged approach for code retrieval with summary generation and commit message automation services.",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "5db7c7d9124f786601136f80ff14882e5845e6de",
    "message": "Add `pyproject.toml` with Poetry configuration and dependencies\n\n- Initialize `pyproject.toml` for the `businessmachine-work` project.\n- Configure Poetry with project metadata, including name, version, description, authors, and license.\n- Specify Python version compatibility (^3.8) and add dependencies for LangChain, OpenAI, and Anthropic.",
    "files": [
      "pyproject.toml"
    ]
  },
  {
    "oid": "0a099058ca3c458bf31f1db2792de02289016bb7",
    "message": "Refactor README.md to clarify commit message generation process and remove outdated file structure information.",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "095cbd39bf305d64a13ee74727b8fd589fe2800d",
    "message": "Update README: Refine project structure explanation, clarify file retrieval, and enhance example prompts.",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "692f9da7f9c85d8f13abf719b52689ddc769fecf",
    "message": "Update README",
    "files": [
      "README.md"
    ]
  },
  {
    "oid": "d780af879ae1967e565861d0426ed864aaddf35a",
    "message": "Initial commit",
    "files": [
      "Dockerfile",
      "README.md",
      "lib/__init__.py",
      "lib/ai/__init__.py",
      "lib/indexer/__init__.py",
      "lib/vcs/__init__.py",
      "lib/vcs/git_commit_parser.py",
      "poetry.lock",
      "pyproject.toml",
      "scripts/cosine_similarity_match.py",
      "scripts/cosine_similarity_match_commits.py",
      "scripts/embedd_commits.py",
      "scripts/embedd_text.py",
      "scripts/git_commit_parser.py",
      "scripts/git_commit_parser_up_to_depth.py",
      "scripts/langchain_usage.py"
    ]
  }
]

parser = GitCommitParser(sample_json)
repo_path = '.'  # Path to your git repository
depth = 1000  # Maximum depth or level of commits to retrieve

parser.add_commits_to_log(repo_path, depth)  # Add new commits to the beginning of the log
print(json.dumps(parser.commits, indent=2))
