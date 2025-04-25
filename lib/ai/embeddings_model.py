import logging
from typing import List
from pydantic import HttpUrl
from langchain_openai import OpenAIEmbeddings
import json
import os

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer  # Import AutoTokenizer


class EmbeddingModel:
    def __init__(
        self,
        embeddings_model_api_key: str,
        embedding_model_base_url: HttpUrl,
        embeddings_model: str = "all-MiniLM-L6-v2",   # <<<<<<<<<<<< DEFAULT CHANGED HERE
        use_mock_llm: bool = False
    ):
        """
        Initialize the EmbeddingModel for generating embeddings.

        :param embeddings_model_api_key: The API key for accessing the embeddings model.
        :param embedding_model_base_url: The base URL for the embeddings model API.
        :param embeddings_model: The model to use for generating embeddings.
        :param use_mock_llm: Whether to use a mock LLM for testing (only returns placeholder embedding)
        """

        self.logger = logging.getLogger(__name__)
        self.use_mock_llm = use_mock_llm
        self.embeddings_model = embeddings_model
        self.max_tokens = 512  # Maximum token limit for all-MiniLM-L6-v2

        self.logger.debug(f"Constructing EmbeddingModel with use_mock_llm: {self.use_mock_llm}")

        if not use_mock_llm:
            if embeddings_model == "text-embedding-3-large":
                # Use OpenAI for this specific model
                self.embeddings_model_api_key = embeddings_model_api_key
                self.embedding_generator = OpenAIEmbeddings(
                    openai_api_key=self.embeddings_model_api_key,
                    base_url=str(embedding_model_base_url),
                    model=embeddings_model
                )
            else:

                # Use HuggingFace directly for all-MiniLM-L6-v2 instead of local path
                if embeddings_model == "all-MiniLM-L6-v2":
                    model_name = 'sentence-transformers/all-MiniLM-L6-v2'

                    # You can optionally set a specific cache directory
                    cache_dir = "/data/users/models/cache"
                    os.makedirs(cache_dir, exist_ok=True)

                    self.logger.info(f"Loading model from HuggingFace with caching at {cache_dir}")
                    # Change cache_dir to cache_folder
                    self.sentence_transformer = SentenceTransformer(model_name, cache_folder=cache_dir)
                    self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
                else:
                    # For any other model, load it normally
                    self.sentence_transformer = SentenceTransformer(embeddings_model)
                    self.tokenizer = AutoTokenizer.from_pretrained(embeddings_model)
        else:
            self.logger.debug("Using mock LLM for embedding generation.")
            self.mock_embedding = self._load_mock_embedding()
            if not self.mock_embedding:
                self.logger.error("Failed to load mock embedding. Placeholder embeddings will be empty.")


    def _truncate_text_to_max_tokens(self, text: str) -> str:
        """
        Truncate the text to fit within the maximum token limit.

        :param text: The input text to be truncated.
        :return: The truncated text.
        """
        if self.embeddings_model == "all-MiniLM-L6-v2" and not self.use_mock_llm:
            try:
                tokens = self.tokenizer.tokenize(text)
                if len(tokens) > self.max_tokens:
                    truncated_tokens = tokens[:self.max_tokens]
                    truncated_text = self.tokenizer.convert_tokens_to_string(truncated_tokens)
                    self.logger.debug(f"Text truncated to {self.max_tokens} tokens.")
                    return truncated_text
            except Exception as e:
                self.logger.warning(f"Failed to truncate text: {str(e)}")
        return text

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
                    return []  # Return empty embedding in case of error
                return embedding
        except FileNotFoundError:
            self.logger.error(f"Placeholder embedding file not found at {filepath}.")
            return []  # Return empty embedding in case of error
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from placeholder embedding file at {filepath}. Please ensure it's valid JSON.")
            return []  # Return empty embedding in case of error

    def embed_list_of_text(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        :param texts: List of strings to generate embeddings for.
        :return: A list of embeddings corresponding to each input text.
        """
        if not texts:
            self.logger.info("No texts provided for embedding.")
            return []


        # Truncate and validate texts
        texts_to_embed = [self._truncate_text_to_max_tokens(text) for text in texts if isinstance(text, str) and text.strip()]
        if not texts_to_embed:
            self.logger.info("All provided texts are empty or invalid.")
            return []

        if self.use_mock_llm:
            if not hasattr(self, 'mock_embedding') or not self.mock_embedding:
                self.logger.error("Mock embedding not available. Returning empty list.")
                return []
            embeddings = [self.mock_embedding.copy() for _ in texts_to_embed]  # Create a copy for each text to avoid reference issues

            self.logger.debug(f"Using mock embeddings for {len(texts_to_embed)} texts.")

        else:
            if self.embeddings_model == "text-embedding-3-large":
                # Generate embeddings using OpenAI API
                embeddings = self.embedding_generator.embed_documents(texts_to_embed)
                self.logger.debug(f"Generated embeddings for {len(texts_to_embed)} texts using OpenAI API.")
            else:
                # Generate embeddings using SentenceTransformer
                embeddings = self.sentence_transformer.encode(texts_to_embed, normalize_embeddings=True).tolist()
                self.logger.debug(f"Generated embeddings for {len(texts_to_embed)} texts using SentenceTransformer.")
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
            if not hasattr(self, 'mock_embedding') or not self.mock_embedding:
                self.logger.error("Mock embedding not available. Returning empty list.")
                return []

            self.logger.debug(f"Using mock embedding for the input text.")
            return self.mock_embedding.copy()  # Return a copy to prevent unintended modifications

        else:
            if self.embeddings_model == "text-embedding-3-large":
                # Generate embedding using OpenAI API
                embedding = self.embedding_generator.embed_query(text)
                self.logger.debug(f"Generated embedding for the input text using OpenAI API.")
            else:

                text_to_embed = self._truncate_text_to_max_tokens(text)
                # Generate embedding using SentenceTransformer
                embedding = self.sentence_transformer.encode(text_to_embed, normalize_embeddings=True).tolist()

                # Ensure embedding is a flat list of floats
                if isinstance(embedding, list) and embedding and isinstance(embedding[0], list):
                    self.logger.debug("Flattening embedding from 2D to 1D list")
                    embedding = embedding[0]

                self.logger.debug(f"Generated embedding for the input text using SentenceTransformer.")
            return embedding

    def count_tokens(self, text: str) -> int:
        """
        Count how many tokens the given text would use when processed by the all-MiniLM-L6-v2 model.

        :param text: The input text to count tokens for
        :return: The number of tokens in the text according to all-MiniLM-L6-v2's tokenizer
        """
        if not isinstance(text, str) or not text.strip():
            self.logger.info("Invalid input: text must be a non-empty string.")
            return 0


        if self.embeddings_model == "all-MiniLM-L6-v2" and not self.use_mock_llm:
            try:
                # Use the tokenizer to count tokens
                tokens = self.tokenizer.tokenize(text)
                return len(tokens)
            except Exception as e:
                self.logger.warning(f"Failed to count tokens for all-MiniLM-L6-v2: {str(e)}")
                # Fall back to simple whitespace-based estimation if tokenization fails
                return len(text.split())

        self.logger.warning("Cannot get exact token count - not using the all-MiniLM-L6-v2 model. Returning approximate word count.")
        return len(text.split())
