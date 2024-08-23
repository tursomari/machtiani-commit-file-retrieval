import os
import json
import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

print("Script is running")

# Load environment variables from a .env file
load_dotenv()

# Set up your OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Initialize the OpenAIEmbeddings object with the API key
embedding_generator = OpenAIEmbeddings(openai_api_key=openai_api_key, model="text-embedding-3-large")

# Function to calculate cosine similarity
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# Load the embeddings from the JSON file
with open('embeddings.json', 'r') as f:
    embeddings_dict = json.load(f)

# The text you want to match
input_text = f"Update my python project config to use python 3.9 to 4.0."
print(f"prompt: {input_text}")

# Generate the embedding for the input text
input_embedding = embedding_generator.embed_query(input_text)

# Find the closest match by calculating similarity
closest_match = None
highest_similarity = -1

for key, value in embeddings_dict.items():
    original_text = value["original_text"]
    embedding = value["embedding"]

    # Calculate similarity
    similarity = cosine_similarity(input_embedding, embedding)

    if similarity > highest_similarity:
        highest_similarity = similarity
        closest_match = original_text

# Output the closest match
print(f"The closest match to '{input_text}' is '{closest_match}' with a similarity of {highest_similarity:.4f}")

