import json
import logging
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.indexer.file_summary_indexer import FileSummaryEmbeddingGenerator  # Import the new module
from lib.utils.utilities import read_json_file, write_json_file

logging.basicConfig(level=logging.INFO)

OPENAI_API_KEY = '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'

commits_logs_file_path = 'data/commits_logs.json'  # Path to your JSON file
commits_logs_json = read_json_file(commits_logs_file_path)

commits_embeddings_file_path = 'data/commits_embeddings.json'  # Path to your JSON file
existing_commits_embeddings_json = read_json_file(commits_embeddings_file_path)

generator = CommitEmbeddingGenerator(commits_logs_json, OPENAI_API_KEY, existing_commits_embeddings_json)
updated_commits_embeddings_json = generator.generate_embeddings()

# Write updated logs back to the JSON file
write_json_file(updated_commits_embeddings_json, commits_embeddings_file_path)

# New section for file summaries
files_embeddings_file_path = 'data/files_embeddings.json'  # Path for file summary embeddings
existing_files_embeddings_json = read_json_file(files_embeddings_file_path)

file_summary_generator = FileSummaryEmbeddingGenerator(commits_logs_json, OPENAI_API_KEY, existing_files_embeddings_json)  # Replace with actual API key
updated_files_embeddings_json = file_summary_generator.generate_embeddings()

# Write updated file embeddings back to the JSON file
write_json_file(updated_files_embeddings_json, files_embeddings_file_path)
