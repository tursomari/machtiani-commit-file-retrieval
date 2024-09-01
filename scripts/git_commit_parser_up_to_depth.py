import json
import logging
from lib.vcs.git_commit_parser import GitCommitParser
from lib.utils.utilities import read_json_file, write_json_file

logging.basicConfig(level=logging.INFO)

# Example usage:
file_path = 'data/commit_logs.json'  # Path to your JSON file
commit_logs_json = read_json_file(file_path)

parser = GitCommitParser(commit_logs_json)
repo_path = '.'  # Path to your git repository
depth = 1000  # Maximum depth or level of commits to retrieve

parser.add_commits_to_log(repo_path, depth)  # Add new commits to the beginning of the log

# Write updated logs back to the JSON file
write_json_file(parser.commits, file_path)

# Optional: Print the updated commit logs
print(json.dumps(parser.commits, indent=2))

