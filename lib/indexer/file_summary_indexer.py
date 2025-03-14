import os
import time
import logging
import json
from fastapi import HTTPException
from langchain_openai import OpenAIEmbeddings
from lib.vcs.git_content_manager import GitContentManager
from app.utils import DataDir, send_prompt_to_openai
from concurrent.futures import ThreadPoolExecutor, as_completed

class FileSummaryGenerator:
    def __init__(
        self,
        project_name: str,
        commit_logs,
        llm_model_api_key: str,
        embeddings_model_api_key: str,
        git_project_path: str,
        ignore_files: list = None,
        existing_files_embeddings=None,
        embeddings_model="text-embedding-3-large",
        llm_model="gpt-4o-mini"
    ):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%M:%S"  # Only minutes and seconds
        )
        self.logger = logging.getLogger(__name__)

        self.project_name = project_name
        self.logger.info(f"project_name: {self.project_name}")
        self.commit_logs = commit_logs
        self.embeddings_model = embeddings_model
        self.summary_model = llm_model
        self.git_project_path = git_project_path
        self.ignore_files = ignore_files if ignore_files is not None else []  # Default to empty list

        self.llm_model_api_key = llm_model_api_key
        self.embeddings_model_api_key = embeddings_model_api_key

        self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.embeddings_model_api_key, model=self.embeddings_model)

        self.existing_file_embeddings = existing_files_embeddings if existing_files_embeddings is not None else {}
        self.logger.info(f"Loaded {len(self.existing_file_embeddings)} existing file embeddings.")

        self.files_embeddings_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project_name), "files_embeddings.json")

        if self.ignore_files:
            self.logger.info(f"Ignored files on initialization: {', '.join(self.ignore_files)}")
        else:
            self.logger.info("No files are set to be ignored.")

    def _get_file_content(self, file_path):
        """Retrieve the content of the file at the given path."""
        full_file_path = os.path.join(self.git_project_path, file_path)  # Join with git_project_path
        try:
            with open(full_file_path, 'r') as file:
                return file.read()
        except Exception as e:
            self.logger.error(f"Error reading file {full_file_path}: {e}")
            return None

    def commit_file_summaries_embedding_file(self):
        """Commit the embedding file after handle_load is finished."""
        content_path = DataDir.CONTENT.get_path(self.project_name)
        embedding_file_path =  os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(self.project_name), "files_embeddings.json")

        if not os.path.exists(embedding_file_path):
            self.logger.error(f"Embedding file does not exist at {embedding_file_path}")
            raise FileNotFoundError(f"Embedding file does not exist at {embedding_file_path}")

        # Initialize a GitContentManager for the CONTENT directory
        git_content_manager = GitContentManager(self.project_name)

        # Add and commit the embedding file
        try:

            git_content_manager.add_file(embedding_file_path)
            git_content_manager.commit_and_tag('Saved')
            self.logger.info(f"Successfully added and committed the embedding file at {embedding_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to add and commit the embedding file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to commit the embedding file: {str(e)}")

    def _summarize_content(self, contents):
        """Generate summaries for the given contents using OpenAI's API in parallel."""
        def summarize_single(file_path, content):
            # Check if the content is not empty or just whitespace
            if not content or not content.strip():
                self.logger.warning(f"No text content to summarize for file: {file_path}")
                return "eddf150cd15072ba4a8474209ec090fedd4d79e4"  # Return nonsense

            prompt = f"Summarize this {file_path}:\n{content}"
            try:
                return send_prompt_to_openai(prompt, self.llm_model_api_key, self.summary_model)
            except Exception as e:
                self.logger.error(f"Error generating summary for {file_path}: {e}")
                return "eddf150cd15072ba4a8474209ec090fedd4d79e4"  # Return nonsense

        summaries = [None] * len(contents)  # Initialize a list to hold summaries in order
        max_workers = 10  # Specify the number of threads here

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {executor.submit(summarize_single, file, content): index for index, (file, content) in enumerate(contents)}

            for future in as_completed(future_to_index):
                index = future_to_index[future]  # Get the original index
                try:
                    summary = future.result()
                    summaries[index] = summary  # Place the summary in the correct index
                except Exception as e:
                    self.logger.error(f"Error summarizing content at index '{index}': {e}")

        return summaries

    def _filter_files_from_new_commits(self):
        """Filter files that are associated with the specified new commits."""
        new_files = {}
        for commit in self.commit_logs:
            commit_oid = commit.get('oid')

            self.logger.debug(f"Processing commit OID: {commit_oid}")
            self.logger.debug(f"Files in commit: {commit.get('files', [])}")

            if not commit_oid:
                self.logger.warning("Commit without 'oid' encountered, skipping.")
                continue

            for file in commit.get('files', []):
                # Skip files in the ignore list
                if file in self.ignore_files:
                    self.logger.info(f"File '{file}' is ignored based on the ignore list.")
                    continue

                # Add the file to the new_files dictionary
                # This allows updating the embedding if the file is already present
                new_files[file] = commit_oid  # Store the commit OID for reference

        self.logger.info(f"Found {len(new_files)} files from new commits to embed (excluding ignored files).")
        return new_files

    def generate(self):
        """
        Generate file summaries and return them as a JSON object.
        """
        start_time = time.time()  # Start the timer
        new_files = self._filter_files_from_new_commits()

        if not new_files:
            self.logger.info("No new files to embed.")
            return self.existing_file_embeddings


        # Prepare to collect summaries and file names
        contents = []  # List to hold file contents

        # Loop through new files to gather contents
        for file, commit_oid in new_files.items():
            full_file_path = os.path.join(self.git_project_path, file)  # Join with git_project_path
            if os.path.exists(full_file_path):  # Check if the file exists
                content = self._get_file_content(file)
                if content:
                    contents.append((file, content))  # Collect file and its content
            else:
                self.logger.error(f"File '{file}' does not exist, skipping.")

        if not contents:
            self.logger.info("No contents to summarize.")
            return self.existing_file_embeddings

        # Generate summaries using the updated _summarize_content method
        summaries = self._summarize_content(contents)

        if not summaries:
            self.logger.info("No summaries to embed.")
            return self.existing_file_embeddings

        embeddings = self.embedding_generator.embed_documents(summaries)

        # Update existing file embeddings
        for i, (file, _) in enumerate(contents):
            summary = summaries[i]
            embedding = embeddings[i]

            if file in self.existing_file_embeddings:
                self.logger.info(f"Updating summary and embedding for file: '{file}'")
            else:
                self.logger.info(f"Creating summary and embedding for new file: '{file}'")

            # Update or add the file's summary and embedding
            self.existing_file_embeddings[file] = {
                "summary": summary,
                "embedding": embedding  # Assuming embedding returns a list
            }

        try:
            with open(self.files_embeddings_path, 'w') as f:
                json.dump(self.existing_file_embeddings, f, indent=4)
            self.logger.info(f"Saved embeddings to {self.files_embeddings_path}")
        except Exception as e:
            self.logger.error(f"Error saving embeddings to file: {e}")

        # Save the file summaries embeddings to a file and commit the changes
        self.commit_file_summaries_embedding_file()

        duration = time.time() - start_time  # Calculate the duration
        self.logger.info(f"Generated embeddings for {len(new_files)} files in {duration:.2f} seconds.")
        return self.existing_file_embeddings

