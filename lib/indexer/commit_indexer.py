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
        if not new_commits:
            self.logger.info("No new commits to embed.")
            return self.existing_embeddings, []

        new_commits_with_files = [commit for commit in new_commits if commit.get('files')]
        if not new_commits_with_files:
            self.logger.info("No new commits with changed files to embed.")
            return self.existing_embeddings, []

        # Prepare data structures
        combined_texts = []  # Final texts for each commit
        commit_embeddings = []  # Final embeddings for each commit

        # First collect all texts and cached embeddings by commit
        all_commits_data = []

        for commit in new_commits_with_files:
            # Ensure message is a string
            message = self._ensure_string(commit['message'])

            commit_data = {
                'commit': commit,
                'combined_text': message,
                'cached_embeddings': [],
                'needs_embedding': False
            }

            for file in commit.get('files', []):
                if file in self.summary_cache and 'embedding' in self.summary_cache[file]:
                    self.logger.info(f"Using cached embedding for file: {file}")
                    commit_data['cached_embeddings'].append(self.summary_cache[file]['embedding'])
                else:
                    # If no cached embedding, append the summary text for embedding
                    summaries = commit.get('summaries', [])
                    summaries_text = self._ensure_string(summaries)
                    if summaries_text:
                        commit_data['combined_text'] += " " + summaries_text
                    commit_data['needs_embedding'] = True

            all_commits_data.append(commit_data)

        # Collect all texts that need embedding into a single batch
        texts_to_embed = []
        for commit_data in all_commits_data:
            if commit_data['needs_embedding'] and self._ensure_string(commit_data['combined_text']).strip():
                texts_to_embed.append(commit_data['combined_text'])

        # Make a single batch embedding call
        if texts_to_embed:
            batch_embeddings = self.embedding_generator.embed_documents(texts_to_embed)

            # Distribute embeddings back to their respective commits
            embedding_index = 0
            for commit_data in all_commits_data:
                if commit_data['needs_embedding'] and self._ensure_string(commit_data['combined_text']).strip():
                    commit_data['cached_embeddings'].append(batch_embeddings[embedding_index])
                    embedding_index += 1

        # Update embeddings dictionary
        new_commit_oids = []
        updated_embeddings = self.existing_embeddings.copy()

        # For each commit, update its entry
        for commit_data in all_commits_data:
            commit = commit_data['commit']
            updated_embeddings[commit['oid']] = {
                "messages": commit_data['combined_text'],
                "embeddings": commit_data['cached_embeddings']
            }
            new_commit_oids.append(commit['oid'])
            # Add to combined_texts and commit_embeddings for consistency with original code
            combined_texts.append(commit_data['combined_text'])
            commit_embeddings.append(commit_data['cached_embeddings'])

        duration = time.time() - start_time  # Calculate the duration
        self.logger.info(f"Generated embeddings for {len(new_commits_with_files)} commits in {duration:.2f} seconds.")
        return updated_embeddings, new_commit_oids
