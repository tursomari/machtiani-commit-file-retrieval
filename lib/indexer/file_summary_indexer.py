import os
import logging
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

class FileSummaryEmbeddingGenerator:
    def __init__(self, commit_logs, api_key: str, git_project_path: str, ignore_files: list = None, existing_embeddings=None, embed_model="text-embedding-3-large", summary_model="gpt-4o-mini"):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.commit_logs = commit_logs
        self.embed_model = embed_model
        self.summary_model = summary_model
        self.git_project_path = git_project_path
        self.ignore_files = ignore_files if ignore_files is not None else []  # Default to empty list

        self.openai_api_key = api_key
        self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.openai_api_key, model=self.embed_model)

        self.existing_embeddings = existing_embeddings if existing_embeddings is not None else {}
        self.logger.info(f"Loaded {len(self.existing_embeddings)} existing embeddings.")

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

    def send_prompt_to_openai(self, prompt_text: str) -> str:
        """
        Sends a prompt to OpenAI and returns the response.

        :param prompt_text: The text prompt to send to OpenAI.
        :return: The response from OpenAI as a string.
        """
        # Define the prompt template
        prompt = PromptTemplate(input_variables=["input_text"], template="{input_text}")

        # Initialize OpenAI LLM with the provided API key
        openai_llm = ChatOpenAI(api_key=self.openai_api_key, model=self.summary_model)

        # Chain the prompt and the LLM
        openai_chain = prompt | openai_llm

        # Execute the chain with the invoke method and return the response
        openai_response = openai_chain.invoke({"input_text": prompt_text})
        return openai_response.content

    def _summarize_content(self, file_path, content):
        """Generate a summary for the given content using OpenAI's API."""
        prompt = f"Summarize this {file_path}:\n{content}"
        try:
            summary = self.send_prompt_to_openai(prompt)
            return summary
        except Exception as e:
            self.logger.error(f"Error generating summary for {file_path}: {e}")
            return None

    def _filter_new_files(self):
        """Filter out files that already have embeddings and those on the ignore list."""
        new_files = {}
        for commit in self.commit_logs:
            for file in commit.get('files', []):
                # Skip files in the ignore list
                if file in self.ignore_files:
                    self.logger.info(f"File '{file}' is ignored based on the ignore list.")
                    continue

                # Check if the file already has an embedding
                if file not in self.existing_embeddings:
                    new_files[file] = commit['oid']  # Store the commit OID for reference
                else:
                    self.logger.info(f"File '{file}' already has an embedding.")
        self.logger.info(f"Found {len(new_files)} new files to embed (excluding ignored files).")
        return new_files

    def generate_embeddings(self):
        """
        Generate embeddings for file summaries and return them as a JSON object.
        """
        new_files = self._filter_new_files()

        if not new_files:
            self.logger.info("No new files to embed.")
            return self.existing_embeddings

        # Loop through each new file
        for file in new_files.keys():
            full_file_path = os.path.join(self.git_project_path, file)  # Join with git_project_path
            if os.path.exists(full_file_path):  # Check if the file exists
                content = self._get_file_content(file)
                if content:
                    summary = self._summarize_content(file, content)
                    if summary:
                        embedding = self.embedding_generator.embed_documents([summary])  # Create embeddings for the summary
                        self.existing_embeddings[file] = {
                            "summary": summary,
                            "embedding": embedding[0]  # Assuming embedding returns a list
                        }
            else:
                self.logger.error(f"File '{file}' does not exist, skipping.")

        self.logger.info(f"Generated embeddings for {len(new_files)} new files.")
        return self.existing_embeddings

