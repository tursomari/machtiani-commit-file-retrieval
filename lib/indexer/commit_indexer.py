import time
import logging
from typing import Dict, List, Union
from pydantic import HttpUrl
from lib.ai.embeddings_model import EmbeddingModel
from lib.utils.utilities import validate_commits_embeddings

class CommitEmbeddingGenerator:
    def __init__(self, commit_logs, embeddings_model_api_key: str, embeddings_model_base_url: HttpUrl, existing_commits_embeddings=None, embeddings_model="text-embedding-3-large", files_embeddings: Dict[str, str] = {}):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.commit_logs = commit_logs
        self.embeddings_model = embeddings_model
        self.embeddings_model_api_key = embeddings_model_api_key

        # Use EmbeddingModel instead of OpenAIEmbeddings
        self.embedding_generator = EmbeddingModel(
            embeddings_model_api_key=self.embeddings_model_api_key,
            embedding_model_base_url=embeddings_model_base_url,
            embeddings_model=self.embeddings_model
        )

        self.existing_commits_embeddings = existing_commits_embeddings if existing_commits_embeddings is not None else {}
        self.files_embeddings_cache = files_embeddings

        if self.existing_commits_embeddings:
             # Validate the embeddings JSON before returning
             try:
                 validate_commits_embeddings(self.existing_commits_embeddings)
             except AssertionError as e:
                 self.logger.error(f"Embeddings JSON validation failed: {e}")
                 raise


    def _filter_new_commits(self):
        new_commits = [commit for commit in self.commit_logs if commit['oid'] not in self.existing_commits_embeddings]
        self.logger.info(f"Found {len(new_commits)} new commits to embed.")
        return new_commits

    def _ensure_string(self, text: Union[str, list]) -> str:
        if isinstance(text, list):
            return " ".join([str(item) for item in text if item])
        return str(text) if text is not None else ""

    def generate_embeddings(self):
        start_time = time.time()
        new_commits = self._filter_new_commits()
        new_commits_with_files = new_commits  # Process all new commits

        if not new_commits_with_files:
            self.logger.info("No new commits to embed.")
            return self.existing_commits_embeddings, []

        all_commits_data = []

        for commit in new_commits_with_files:
            original_messages = commit['message'] if isinstance(commit['message'], list) else [commit['message']]
            summaries = commit.get('summaries', [])
            files = commit.get('files', [])

            # Include ALL summaries in the messages list
            all_messages = original_messages.copy()
            all_messages.extend(summaries)

            # Track embeddings for this commit
            cached_embeddings = []
            texts_to_embed = []

            # 1. Always embed original messages
            texts_to_embed.extend(original_messages)

            # 2. Process summaries (check if their files are cached)
            uncached_summaries = []
            for j, summary in enumerate(summaries):
                # Check if there's a corresponding cached file
                if j < len(files) and files[j] in self.files_embeddings_cache:
                    # Use cached embedding for this summary
                    cached_embeddings.append(self.files_embeddings_cache[files[j]]['embedding'])
                else:
                    # Add to texts_to_embed to generate embedding
                    uncached_summaries.append(summary)

            # Add uncached summaries to the embedding batch
            texts_to_embed.extend(uncached_summaries)

            # Store data for this commit
            commit_data = {
                'commit': commit,
                'all_messages': all_messages,
                'texts_to_embed': texts_to_embed,
                'cached_embeddings': cached_embeddings,
                'needs_embedding': bool(texts_to_embed)  # True if any text needs embedding
            }
            all_commits_data.append(commit_data)

        # Batch embed all texts across commits
        texts_to_embed_global = []
        commit_indices = []
        for i, commit_data in enumerate(all_commits_data):
            if commit_data['needs_embedding']:
                for text in commit_data['texts_to_embed']:
                    text_str = self._ensure_string(text)
                    if text_str.strip():
                        texts_to_embed_global.append(text_str)
                        commit_indices.append(i)

        # Generate embeddings in a single batch using the new embedding model
        batch_embeddings = []
        if texts_to_embed_global:
            batch_embeddings = self.embedding_generator.embed_list_of_text(texts_to_embed_global)

        # Distribute embeddings back to commits
        embeddings_iter = iter(batch_embeddings)
        for i, commit_data in enumerate(all_commits_data):
            if commit_data['needs_embedding']:
                # Calculate how many embeddings this commit needs
                num_needed = len(commit_data['texts_to_embed'])
                generated = [next(embeddings_iter) for _ in range(num_needed)]

                # Reconstruct the full embeddings list:
                # [original_msg_embeddings] + [uncached_summary_embeddings] + [cached_summary_embeddings]
                final_embeddings = []

                # Split generated into original and uncached summaries
                num_original = len(commit_data['texts_to_embed']) - len(commit_data['cached_embeddings'])
                original_embeddings = generated[:len(original_messages)]
                summary_embeddings = generated[len(original_messages):]

                # Merge with cached embeddings
                final_embeddings.extend(original_embeddings)
                final_embeddings.extend(summary_embeddings)
                final_embeddings.extend(commit_data['cached_embeddings'])

                commit_data['final_embeddings'] = final_embeddings
            else:
                commit_data['final_embeddings'] = commit_data['cached_embeddings']

        # Update the global embeddings
        updated_embeddings = self.existing_commits_embeddings.copy()
        new_commit_oids = []

        for commit_data in all_commits_data:
            commit = commit_data['commit']
            updated_embeddings[commit['oid']] = {
                "messages": commit_data['all_messages'],
                "embeddings": commit_data['final_embeddings']
            }
            new_commit_oids.append(commit['oid'])

        # Validate the embeddings JSON before returning
        try:
            validate_commits_embeddings(updated_embeddings)
        except AssertionError as e:
            self.logger.error(f"Embeddings JSON validation failed: {e}")
            raise

        duration = time.time() - start_time
        self.logger.info(f"Generated embeddings for {len(new_commits_with_files)} commits in {duration:.2f} seconds.")
        return updated_embeddings, new_commit_oids
