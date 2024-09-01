import json
import logging
import argparse
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.utils.utilities import read_json_file, write_json_file

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Match a commit to the input text using embeddings.")
    parser.add_argument('input_text', type=str, help="The input text to find the closest commit match.")

    # Parse the arguments
    args = parser.parse_args()

    # Initialize the CommitEmbeddingMatcher
    matcher = CommitEmbeddingMatcher(embeddings_file='data/commits_embeddings.json')

    # Match the commit based on input text
    matcher.match_commit(args.input_text)

if __name__ == "__main__":
    main()

