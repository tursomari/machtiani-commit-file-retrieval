import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# Load environment variables from .env file
load_dotenv()

# Get API keys from environment variables
openai_api_key = os.getenv('OPENAI_API_KEY')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')

# Define the prompt template
prompt = PromptTemplate(input_variables=["input_text"], template="Translate the following text to French: '{input_text}'")

# Initialize OpenAI LLM
openai_llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4o-mini")

# Initialize Anthropic LLM
#anthropic_llm = ChatAnthropic(model="claude-3-opus-20240229", api_key=anthropic_api_key)

# Chain the prompt and the LLMs using RunnableSequence
openai_chain = prompt | openai_llm
#anthropic_chain = prompt | anthropic_llm

# Input text for the query
input_text = "Hello, how are you?"

# Execute the chain with the invoke method for OpenAI
openai_response = openai_chain.invoke({"input_text": input_text})
print(f"OpenAI response: {openai_response}")

# Execute the chain with the invoke method for Anthropic
#anthropic_response = anthropic_chain.invoke({"input_text": input_text})
#print(f"Anthropic response: {anthropic_response}")

