import os
import time
import json
import logging
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

class CommitEmbeddingGenerator:
    def __init__(self, commit_logs, api_key: str, existing_embeddings=None, model="text-embedding-3-large"):
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

    def _filter_new_commits(self):
        """Filter out commits that already have embeddings."""
        new_commits = [commit for commit in self.commit_logs if commit['oid'] not in self.existing_embeddings]
        self.logger.info(f"Found {len(new_commits)} new commits to embed.")
        return new_commits

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

        # Rename variable to clarify it holds commit embeddings.
        commit_embeddings = []
        # Combine commit messages and summaries for each commit.
        combined_texts = [
            commit['message'] + commit.get('summaries', [])
            for commit in new_commits_with_files
        ]

        self.logger.info(f"combined_texts type {type(combined_texts)}")
        self.logger.info(f"combined_texts {combined_texts}")

        # Generate embeddings for each set of combined texts.
        for texts in combined_texts:
            # Each call to embed_documents returns an array of embeddings corresponding
            # one-to-one with the texts.
            commit_embeddings.append(self.embedding_generator.embed_documents(texts))

        new_commit_oids = []
        # Create a copy of existing_embeddings to avoid side effects.
        updated_embeddings = self.existing_embeddings.copy()

        # For each commit, update its entry with both the combined texts and the embeddings.
        for commit, embed_list, texts in zip(new_commits_with_files, commit_embeddings, combined_texts):
            updated_embeddings[commit['oid']] = {
                "messages": texts,       # Combined commit messages and summaries.
                "embeddings": embed_list # The corresponding embeddings.
            }
            new_commit_oids.append(commit['oid'])

        duration = time.time() - start_time  # Calculate the duration
        self.logger.info(f"Generated embeddings for {len(new_commits_with_files)} commits in {duration:.2f} seconds.")
        return updated_embeddings, new_commit_oids

