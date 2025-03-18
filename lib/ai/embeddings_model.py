import logging
from typing import List
from langchain_openai import OpenAIEmbeddings

class EmbeddingModel:
    def __init__(self, embeddings_model_api_key: str, embeddings_model="text-embedding-3-large"):
        """
        Initialize the LlmModel for generating embeddings.

        :param embeddings_model_api_key: The API key for accessing the embeddings model.
        :param embeddings_model: The OpenAI model to use for generating embeddings.
        """
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Set up your OpenAI API key and model for embeddings
        self.embeddings_model_api_key = embeddings_model_api_key
        self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.embeddings_model_api_key, model=embeddings_model)

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

        # Generate embeddings
        embeddings = self.embedding_generator.embed_documents(texts_to_embed)
        self.logger.info(f"Generated embeddings for {len(texts_to_embed)} texts.")
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

        # Generate embedding
        embedding = self.embedding_generator.embed_query(text)
        self.logger.info(f"Generated embedding for the input text.")
        return embedding
