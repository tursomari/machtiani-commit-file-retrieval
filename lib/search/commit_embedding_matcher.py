import os
import json
import numpy as np
from dotenv import load_dotenv
from lib.utils.enums import MatchStrength
from lib.ai.embeddings_model import EmbeddingModel
from typing import List
from pydantic import HttpUrl
import logging
import asyncio  # Import asyncio for asynchronous operations

logger = logging.getLogger(__name__)

class CommitEmbeddingMatcher:
    def __init__(self, commits_embedding_filepath: str, embeddings_model_api_key: str, embedding_model_base_url: HttpUrl, embeddings_model: str = "all-MiniLM-L6-v2"):
        # Set up your OpenAI API key
        if embeddings_model_api_key:
            self.embeddings_model_api_key = embeddings_model_api_key
            self.embedding_generator = EmbeddingModel(embeddings_model_api_key=self.embeddings_model_api_key, embedding_model_base_url=embedding_model_base_url, embeddings_model=embeddings_model)
            self.embeddings_dict = self.load_embeddings(commits_embedding_filepath)
        else:
            raise ValueError("OpenAI API key not found. Please set it in the environment or pass it explicitly.")

    def load_embeddings(self, filepath: str) -> dict:
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Embeddings file not found: {filepath}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from embeddings file: {filepath}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading embeddings: {e}")
            raise

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    async def find_closest_commits(self, input_text: str, match_strength: MatchStrength, top_n: int = 10) -> list:
        logger.warning("Using the host's OpenAI API key for finding closest commits.")
        input_embedding = await asyncio.to_thread(self.embedding_generator.embed_text, input_text)
        min_similarity = match_strength.get_min_similarity()

        matches = []

        # Iterate over each commit's entry.
        # Each entry now contains a list of embeddings under the key "embeddings".
        for oid, value in self.embeddings_dict.items():
            embeddings = value["embeddings"]

            # Compute the similarity for each embedding in the list
            # and select the maximum similarity.
            max_similarity = max(self.cosine_similarity(input_embedding, emb) for emb in embeddings)

            # If the maximum similarity meets the threshold, add this commit.
            if max_similarity >= min_similarity:
                matches.append({"oid": oid, "similarity": max_similarity})

        # Sort matches by similarity in descending order and return the top_n matches.
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:top_n]
