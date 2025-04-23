import os
import re
import logging
import json
import asyncio
from openai import OpenAI, AsyncOpenAI # Changed import
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionChunk # Added for type hinting

# Set up logging
#logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LlmModel:
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", temperature: float = None, timeout: int = 3600, max_retries: int = 5, use_mock_llm: bool = False, max_tokens: int = None):
        """
        Initialize the LlmModel with OpenAI clients.

        Args:
            api_key (str): API key for authentication with the provider.
            base_url (str): Base URL of the API endpoint (default: "https://api.openai.com/v1").
            model (str): The model name to use (default: "gpt-4o-mini").
            temperature (float, optional): Controls randomness of output. If None, API default is used.
            timeout (int): Request timeout in seconds (default: 3600).
            max_retries (int): Maximum number of retries for failed requests (default: 5).
            use_mock_llm (bool): If True, methods will return mock responses instead of calling OpenAI.
            max_tokens (int, optional): Maximum number of tokens to generate.
        """
        self.openai_api_key = api_key
        logger.info(f"\n\nnBase URL of 'openai': {base_url}\n\n\n")
        self.base_url = base_url
        self.model = model
        self.temperature = temperature # Keep temperature stored
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_mock_llm = use_mock_llm
        self.max_tokens = max_tokens
        logger.info(f"Constructing LlmModel with use_mock_llm: {self.use_mock_llm}")


        # If you're hitting the official openai.com endpoint, omit `base_url` entirely
        # and let the library use its own default of https://api.openai.com/v1
        is_official = bool(re.search(r"openai\.com", self.base_url, re.IGNORECASE))
        if is_official:
            logger.info("Detected official OpenAI API hostname; not passing base_url.")
            client_kwargs = {
                "base_url": "https://api.openai.com/v1",
                "api_key": self.openai_api_key,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            }
        else:
            logger.info("Non‑OpenAI endpoint; passing custom base_url.")
            #self.base_url = self._ensure_protocol(base_url)  # Ensure base URL has a protocol
            client_kwargs = {
                "api_key": self.openai_api_key,
                "base_url": self.base_url,
                #"base_url": "https://api.openai.com/v1",
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            }

        self.sync_client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

    def _ensure_protocol(self, url: str) -> str:
        """Ensure the URL has a protocol (http:// or https://)."""
        if not url.startswith(("http://", "https://")):
            logger.warning(f"Adding 'https://' to base_url '{url}'")
            return f"https://{url}"  # Default to https
        return url

    def _prepare_request_params(self, **extra_params):
        """Helper to prepare common request parameters."""
        params = {
            "model": self.model,
            **extra_params
        }
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        return params

    def send_prompt(self, prompt_text: str):
        """
        Send a prompt using the synchronous OpenAI client.


        Args:
            prompt_text (str): The text prompt to send.

        Returns:
            str: The response content from the LLM.
        """
        if self.use_mock_llm:
            logger.debug(f"Using mock LLM for sync prompt: {prompt_text[:50]}...")
            # Return a simple mock response, maybe based on the prompt length or content
            return f"Mock response for: {prompt_text[:100]}"

        messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt_text}]
        request_params = self._prepare_request_params(messages=messages)

        try:
            logger.debug(f"Sending sync request with params: { {k:v for k,v in request_params.items() if k != 'messages'} }")
            response = self.sync_client.chat.completions.create(**request_params)
            content = response.choices[0].message.content
            logger.debug(f"Received sync response: {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"Error during sync OpenAI call: {e}")
            # Consider re-raising or returning a specific error message
            raise

    async def send_prompt_async(self, prompt_text: str):
        """
        Send a prompt using the asynchronous OpenAI client.


        Args:
            prompt_text (str): The text prompt to send.

        Returns:
            str: The response content from the LLM.
        """
        if self.use_mock_llm:
            logger.debug(f"Using mock LLM for async prompt: {prompt_text[:50]}...")
            # Simulate async operation slightly
            await asyncio.sleep(0.01)
            return f"Mock async response for: {prompt_text[:100]}"

        messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt_text}]
        request_params = self._prepare_request_params(messages=messages)

        try:
            logger.debug(f"Sending async request with params: { {k:v for k,v in request_params.items() if k != 'messages'} }")
            response = await self.async_client.chat.completions.create(**request_params)
            content = response.choices[0].message.content
            logger.debug(f"Received async response: {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"Error during async OpenAI call: {e}")
            # Consider re-raising or returning a specific error message
            raise

    async def send_prompt_streaming(
        self,
        prompt_text: str,
    ):
        """
        Send a prompt to the OpenAI API and stream the response using the async client.

        Args:
            prompt_text (str): The text prompt to send.

        Yields:
            str: A JSON-formatted string containing each token delta as it streams.
        """
        if self.use_mock_llm:
            logger.debug(f"Using mock LLM for streaming prompt: {prompt_text[:50]}...")
            mock_response = f"Mock stream response for: {prompt_text[:100]}"
            for word in mock_response.split():
                yield json.dumps({"token": word + " "})
                await asyncio.sleep(0.05) # Simulate streaming delay
            return # End the generator

        messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt_text}]
        request_params = self._prepare_request_params(messages=messages, stream=True)

        try:
            logger.debug(f"Sending streaming request with params: { {k:v for k,v in request_params.items() if k != 'messages'} }")
            stream = await self.async_client.chat.completions.create(**request_params)

            async for chunk in stream:
                # Added check for chunk content because sometimes the first chunk might be empty
                # or contain metadata without actual text delta.
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    # Yield each token delta as a JSON-formatted string
                    yield json.dumps({"token": token})
            logger.debug("Finished streaming response.")

        except Exception as e:
            logger.error(f"Error during streaming OpenAI call: {e}")
            # Decide how to handle errors in streaming: yield an error message, raise, or log and stop.
            # Yielding an error message might be suitable for some UIs.
            yield json.dumps({"error": str(e)})
            # Or re-raise if the caller should handle it:
            # raise
