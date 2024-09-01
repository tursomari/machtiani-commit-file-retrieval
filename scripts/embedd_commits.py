import json
import logging
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.utils.utilities import read_json_file, write_json_file

logging.basicConfig(level=logging.INFO)

commit_logs_file_path = 'data/commit_logs.json'  # Path to your JSON file
commit_logs_json = read_json_file(commit_logs_file_path)

commits_embeddings_file_path = 'data/commits_embeddings.json'  # Path to your JSON file
existing_commits_embeddings_json = read_json_file(commits_embeddings_file_path)

generator = CommitEmbeddingGenerator(commit_logs_json, existing_commits_embeddings_json)
updated_commits_embeddings_json = generator.generate_embeddings()

# Write updated logs back to the JSON file
write_json_file(updated_commits_embeddings_json, commits_embeddings_file_path)

# Example usage:
# commit_logs = [...]  # List of commit dictionaries
# existing_embeddings = {...}  # JSON object with existing embeddings
# generator = CommitEmbeddingGenerator(commit_logs, existing_embeddings)
# updated_embeddings = generator.generate_embeddings()
