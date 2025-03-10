import os
import time
import json
import logging
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from lib.indexer.file_summary_indexer import FileSummaryGenerator
from typing import Dict, List, Union
from app.utils import (
    DataDir,
    retrieve_file_contents,
)

class CommitEmbeddingGenerator:
    def __init__(self, commit_logs, api_key: str, existing_embeddings=None, model="text-embedding-3-large", files_summaries_json: Dict[str, str] = {},):
        """
        Initialize the CommitEmbeddingGenerator with commit logs and an optional existing embeddings JSON object.

        :param commit_logs: List of commit objects, each with an 'oid' and 'message' key.
        :param existing_embeddings: A JSON object containing existing embeddings (defaults to an empty dictionary).
        :param model: The OpenAI model to use for generating embeddings.
        """
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.commit_logs = commit_logs
        self.model = model

        # Set up your OpenAI API key
        self.openai_api_key = api_key
        self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.openai_api_key, model=self.model)

        # Use the provided existing embeddings or start with an empty dictionary
        self.existing_embeddings = existing_embeddings if existing_embeddings is not None else {}
        self.summary_cache = files_summaries_json

    def _filter_new_commits(self):
        """Filter out commits that already have embeddings."""
        new_commits = [commit for commit in self.commit_logs if commit['oid'] not in self.existing_embeddings]
        self.logger.info(f"Found {len(new_commits)} new commits to embed.")
        return new_commits

    def _ensure_string(self, text: Union[str, list]) -> str:
        """Ensure that text is a string, converting from list if necessary."""
        if isinstance(text, list):
            return " ".join([str(item) for item in text if item])
        return str(text) if text is not None else ""

    def generate_embeddings(self):
        start_time = time.time()  # Start the timer
        new_commits = self._filter_new_commits()

        # If there are no new commits, return early
        new_commits_with_files = [c for c in new_commits if c.get('files')]
        if not new_commits_with_files:
            self.logger.info("No new commits with changed files to embed.")
            return self.existing_embeddings, []

        # Prepare data structures
        all_commits_data = []

        # First collect all texts and cached embeddings by commit
        for commit in new_commits_with_files:
            # Handle 'message' as a list
            messages = commit['message'] if isinstance(commit['message'], list) else [commit['message']]

            commit_data = {
                'commit': commit,
                'messages': messages,  # Store the original list of messages
                'cached_embeddings': [],
                'needs_embedding': False
            }

            # Get any summaries (also potentially a list)
            summaries = commit.get('summaries', [])
            if summaries:
                if not isinstance(summaries, list):
                    summaries = [summaries]
                commit_data['messages'].extend(summaries)

            # Check for cached embeddings for files
            for file in commit.get('files', []):
                if file in self.summary_cache and 'embedding' in self.summary_cache[file]:
                    self.logger.info(f"Using cached embedding for file: {file}")
                    commit_data['cached_embeddings'].append(self.summary_cache[file]['embedding'])
                else:
                    commit_data['needs_embedding'] = True

            all_commits_data.append(commit_data)

        # Collect all texts that need embedding into a single batch
        texts_to_embed = []
        commit_indices = []  # Track which commit each text belongs to

        for i, commit_data in enumerate(all_commits_data):
            if commit_data['needs_embedding']:
                # Add all messages from this commit that need embedding
                for message in commit_data['messages']:
                    message_str = self._ensure_string(message)
                    if message_str.strip():
                        texts_to_embed.append(message_str)
                        commit_indices.append(i)

        # Make a single batch embedding call
        if texts_to_embed:
            batch_embeddings = self.embedding_generator.embed_documents(texts_to_embed)

            # Distribute embeddings back to their respective commits
            for i, embedding in enumerate(batch_embeddings):
                commit_index = commit_indices[i]
                all_commits_data[commit_index]['cached_embeddings'].append(embedding)

        # Update embeddings dictionary
        new_commit_oids = []
        updated_embeddings = self.existing_embeddings.copy()

        # For each commit, update its entry
        for commit_data in all_commits_data:
            commit = commit_data['commit']
            updated_embeddings[commit['oid']] = {
                "messages": commit_data['messages'],  # Already a list of messages
                "embeddings": commit_data['cached_embeddings']  # List of embeddings
            }
            new_commit_oids.append(commit['oid'])

        duration = time.time() - start_time  # Calculate the duration
        self.logger.info(f"Generated embeddings for {len(new_commits_with_files)} commits in {duration:.2f} seconds.")
        return updated_embeddings, new_commit_oids
