import logging
from typing import List
from pydantic import HttpUrl
from langchain_openai import OpenAIEmbeddings
import json
import os

class EmbeddingModel:
    def __init__(self, embeddings_model_api_key: str, embedding_model_base_url: HttpUrl, embeddings_model="text-embedding-3-large", use_mock_llm: bool = False):
        """
        Initialize the EmbeddingModel for generating embeddings.

        :param embeddings_model_api_key: The API key for accessing the embeddings model.
        :param embedding_model_base_url: The base URL for the embeddings model API.
        :param embeddings_model: The OpenAI model to use for generating embeddings.
        :param use_mock_llm: A boolean indicating whether to use a mock LLM for testing, defaults to False.
        """
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.use_mock_llm = use_mock_llm
        if not use_mock_llm:
            # Set up your OpenAI API key and model for embeddings
            self.embeddings_model_api_key = embeddings_model_api_key
            self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.embeddings_model_api_key, base_url=str(embedding_model_base_url), model=embeddings_model)
        else:
            self.logger.info("Using mock LLM for embedding generation.")

    def _load_mock_embedding(self) -> List[float]:
        """
        Loads a placeholder embedding from data/embedding_placeholder.json.

        :return: A list of floats representing the placeholder embedding.
        """
        filepath = "data/embedding_placeholder.json"
        if not os.path.exists("data"):
            os.makedirs("data")
        if not os.path.exists(filepath):
            # Create a dummy placeholder file if it doesn't exist
            with open(filepath, 'w') as f:
                json.dump([0.1, 0.2, 0.3], f)
            self.logger.warning(f"Placeholder embedding file not found at {filepath}. Creating a default one.")


        try:
            with open(filepath, 'r') as f:
                embedding = json.load(f)
                if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
                    self.logger.error(f"Invalid format in placeholder embedding file at {filepath}. It should be a list of floats.")
                    return [] # Return empty embedding in case of error
                return embedding
        except FileNotFoundError:
            self.logger.error(f"Placeholder embedding file not found at {filepath}.")
            return [] # Return empty embedding in case of error
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from placeholder embedding file at {filepath}. Please ensure it's valid JSON.")
            return [] # Return empty embedding in case of error


    def embed_list_of_text(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        :param texts: List of strings to generate embeddings for.
        :return: A list of embeddings corresponding to each input text.
        """
        if not texts:
            self.logger.info("No texts provided for embedding.")
            return []

        # Ensure that all texts are non-empty strings
        texts_to_embed = [text for text in texts if isinstance(text, str) and text.strip()]
        if not texts_to_embed:
            self.logger.info("All provided texts are empty or invalid.")
            return []

        if self.use_mock_llm:
            placeholder_embedding = self._load_mock_embedding()
            if not placeholder_embedding: # Handle case where loading failed, return empty list
                return []
            embeddings = [placeholder_embedding] * len(texts_to_embed) # Return the same placeholder embedding for all texts
            self.logger.info(f"Using mock embeddings for {len(texts_to_embed)} texts.")
        else:
            # Generate embeddings using OpenAI API
            embeddings = self.embedding_generator.embed_documents(texts_to_embed)
            self.logger.info(f"Generated embeddings for {len(texts_to_embed)} texts using OpenAI API.")
        return embeddings

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text input.

        :param text: The string to generate an embedding for.
        :return: The embedding corresponding to the input text.
        """
        if not isinstance(text, str) or not text.strip():
            self.logger.info("Invalid input: text must be a non-empty string.")
            return []

        if self.use_mock_llm:
            embedding = self._load_mock_embedding()
            if not embedding: # Handle case where loading failed, return empty list
                return []
            self.logger.info(f"Using mock embedding for the input text.")
        else:
            # Generate embedding using OpenAI API
            embedding = self.embedding_generator.embed_query(text)
            self.logger.info(f"Generated embedding for the input text using OpenAI API.")
        return embedding
