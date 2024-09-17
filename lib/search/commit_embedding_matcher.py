import os
import json
import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from lib.utils.enums import MatchStrength
from typing import List

class CommitEmbeddingMatcher:
    def __init__(self, embeddings_file: str, api_key: str, model: str = "text-embedding-3-large"):
        load_dotenv()  # Load environment variables from a .env file

        # Set up your OpenAI API key
        if api_key:
            self.openai_api_key = api_key
            self.embedding_generator = OpenAIEmbeddings(openai_api_key=self.openai_api_key, model=model)
            self.embeddings_dict = self.load_embeddings(embeddings_file)

        else:
            raise ValueError("OpenAI API key not found. Please set it in the environment or pass it explicitly.")

    def load_embeddings(self, filepath: str) -> dict:
        with open(filepath, 'r') as f:
            return json.load(f)

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def find_closest_commits(self, input_text: str, match_strength: MatchStrength) -> list:
        input_embedding = self.embedding_generator.embed_query(input_text)
        min_similarity = match_strength.get_min_similarity()

        matches = []

        for oid, value in self.embeddings_dict.items():
            embedding = value["embedding"]
            similarity = self.cosine_similarity(input_embedding, embedding)

            if similarity >= min_similarity:
                matches.append({"oid": oid, "similarity": similarity})

        # Sort matches by similarity in descending order
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return matches

    def find_closest_commits_with_embedding(self, input_text: str, input_embedding: List[float], match_strength: MatchStrength) -> list:
        min_similarity = match_strength.get_min_similarity()

        matches = []

        for oid, value in self.embeddings_dict.items():
            embedding = value["embedding"]
            similarity = self.cosine_similarity(np.array(input_embedding), np.array(embedding))

            if similarity >= min_similarity:
                matches.append({"oid": oid, "similarity": similarity})

        # Sort matches by similarity in descending order
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        return matches

# Example usage:
#if __name__ == "__main__":
#    matcher = CommitEmbeddingMatcher(embeddings_file='commits_embeddings.json')
#    input_text = "Update my python project config to use python 3.9 to 4.0."
#    matcher.match_commit(input_text)
#
