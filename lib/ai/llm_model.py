import os
import logging
import json
import asyncio
from typing import AsyncIterator, Optional
import openai

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LlmModel:
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", temperature: float = 0.0, timeout: int = 3600, max_retries: int = 5):
        """
        Initialize the LlmModel with the OpenAI client.

        Args:
            api_key (str): API key for authentication with the provider.
            base_url (str): Base URL of the API endpoint.
            model (str): The model name to use (default: "gpt-4o-mini").
            temperature (float): Controls randomness of output (default: 0.0, deterministic).
            timeout (int): Request timeout in seconds (default: 3600).
            max_retries (int): Maximum number of retries for failed requests (default: 5).
        """
        self.openai_api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.base_url.startswith(('http://', 'https://')):
            self.base_url = 'https://' + self.base_url

        try:
            logger.debug(f"Connecting to OpenAI at URL: {self.base_url}")
            self.client = openai.OpenAI(
                api_key=self.openai_api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}, base_url: {self.base_url}")
            raise

    def send_prompt(self, prompt_text: str) -> str:
        """
        Send a prompt to the OpenAI API.

        Args:
            prompt_text (str): The text prompt to send.

        Returns:
            str: The response content from the LLM.
        """
        try:
            kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt_text}],
            }

            # Handle the 'reason' model specifically
            if self.model != 'o3-mini':
                kwargs["temperature"] = self.temperature

            response = self.client.chat.completions.create(**kwargs)

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error in send_prompt: {e}")
            raise

    async def send_prompt_async(self, prompt_text: str) -> str:
        """
        Send a prompt to the OpenAI API asynchronously.

        Args:
            prompt_text (str): The text prompt to send.

        Returns:
            str: The response content from the LLM.
        """
        try:
            # Create an async client
            async_client = openai.AsyncOpenAI(
                api_key=self.openai_api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries
            )

            kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt_text}],
            }

            # Handle the 'reason' model specifically
            if self.model != 'o3-mini':
                kwargs["temperature"] = self.temperature

            response = await async_client.chat.completions.create(**kwargs)

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error in send_prompt_async: {e}")
            raise

    async def send_prompt_streaming(self, prompt_text: str) -> AsyncIterator[str]:
        """
        Send a prompt to the OpenAI API and stream the response.

        Args:
            prompt_text (str): The text prompt to send.

        Yields:
            str: A JSON-formatted string containing each token as it streams.
        """
        try:
            # Create an async client
            async_client = openai.AsyncOpenAI(
                api_key=self.openai_api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries
            )

            kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt_text}],
                "stream": True
            }

            if self.model != 'o3-mini':
                kwargs["temperature"] = self.temperature

            stream = await async_client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    yield json.dumps({"token": token})

        except Exception as e:
            logger.error(f"Error in send_prompt_streaming: {e}")
            raise
