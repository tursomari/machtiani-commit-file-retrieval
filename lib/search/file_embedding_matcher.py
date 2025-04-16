import os
import json
import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from lib.utils.enums import MatchStrength
from typing import List
import logging
import asyncio  # Import asyncio for asynchronous operations

logger = logging.getLogger(__name__)

class FileEmbeddingMatcher:
    def __init__(self, embeddings_file: str, api_key: str, model: str = "text-embedding-3-large"):
        # Set up your OpenAI API key
        if api_key:
            self.llm_model_api_key = api_key
            self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.llm_model_api_key, model=model)
            self.embeddings_dict = self.load_embeddings(embeddings_file)
        else:
            raise ValueError("OpenAI API key not found. Please set it in the environment or pass it explicitly.")

    def load_embeddings(self, filepath: str) -> dict:
        with open(filepath, 'r') as f:
            return json.load(f)

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    async def find_closest_files(self, input_text: str, match_strength: MatchStrength) -> list:
        logger.warning("Using the host's OpenAI API key for finding closest files.")
        input_embedding = await asyncio.to_thread(self.embedding_generator.embed_query, input_text)
        min_similarity = match_strength.get_min_similarity()

        matches = []

        for oid, value in self.embeddings_dict.items():
            embedding = value["embedding"]
            similarity = self.cosine_similarity(input_embedding, embedding)

            if similarity >= min_similarity:
                matches.append({"path": oid, "similarity": similarity})

        # Sort matches by similarity in descending order
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return matches
