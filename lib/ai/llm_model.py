import os
import logging
import json
import asyncio
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LlmModel:
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", temperature: float = 0.0, timeout: int = 3600, max_retries: int = 5, use_mock_llm: bool = False):
        """
        Initialize the LlmModel with a ChatOpenAI instance.

        Args:
            api_key (str): API key for authentication with the provider.
            base_url (str): Base URL of the API endpoint (default: "https://api.openai.com/v1").
            model (str): The model name to use (default: "gpt-4o-mini").
            temperature (float): Controls randomness of output (default: 0.0, deterministic).
            timeout (int): Request timeout in seconds (default: 3600).
            max_retries (int): Maximum number of retries for failed requests (default: 5).
            use_mock_llm (bool): If True, methods will return "foo bar" instead of calling OpenAI.
        """
        self.openai_api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_mock_llm = use_mock_llm
        logger.info(f"Constructing LlmModel with use_mock_llm: {self.use_mock_llm}")
        # Instantiate ChatOpenAI in the constructor
        self.llm = ChatOpenAI(
            openai_api_key=self.openai_api_key,
            model=self.model,
            openai_api_base=self.base_url,
            request_timeout=self.timeout,
            max_retries=self.max_retries,
            temperature=self.temperature
        )

    def send_prompt(self, prompt_text: str):
        """
        Send a prompt to the pre-initialized ChatOpenAI instance.

        Args:
            prompt_text (str): The text prompt to send.

        Returns:
            str: The response content from the LLM.
        """
        if self.use_mock_llm:
            return "foo bar"

        prompt = PromptTemplate(input_variables=["input_text"], template="{input_text}")
        openai_chain = prompt | self.llm
        openai_response = openai_chain.invoke({"input_text": prompt_text})
        return openai_response.content

    async def send_prompt_async(self, prompt_text: str):
        """
        Send a prompt to the pre-initialized ChatOpenAI instance.

        Args:
            prompt_text (str): The text prompt to send.

        Returns:
            str: The response content from the LLM.
        """
        if self.use_mock_llm:
            return "foo bar"

        prompt = PromptTemplate(input_variables=["input_text"], template="{input_text}")
        openai_chain = prompt | self.llm
        openai_response = await openai_chain.ainvoke({"input_text": prompt_text})
        return openai_response.content

    async def send_prompt_streaming(
        self,
        prompt_text: str,
    ):
        """
        Send a prompt to the OpenAI API and stream the response.

        Args:
            prompt_text (str): The text prompt to send.
            model (str): The model name to use (default: "gpt-4o-mini").
            timeout (int): Request timeout in seconds (default: 3600).
            max_retries (int): Maximum number of retries for failed requests (default: 5).

        Yields:
            str: A JSON-formatted string containing each token as it streams.
        """
        # Define the prompt template
        if self.use_mock_llm:
            yield json.dumps({"token": "foo bar"})
            return

        prompt = PromptTemplate(input_variables=["input_text"], template="{input_text}")

        # Initialize the callback handler for streaming
        callback = AsyncIteratorCallbackHandler()

        # Initialize the ChatOpenAI model with streaming enabled
        openai_llm = ChatOpenAI(
            openai_api_key=self.openai_api_key,
            model=self.model,
            openai_api_base=self.base_url,
            request_timeout=self.timeout,
            max_retries=self.max_retries,
            streaming=True,
            callbacks=[callback],
        )

        # Format the input text using the prompt template
        input_text = prompt.format(input_text=prompt_text)
        messages = [HumanMessage(content=input_text)]

        # Start the asynchronous generation process
        generation_task = asyncio.create_task(openai_llm.agenerate(messages=[messages]))

        # Iterate over the streaming tokens
        async for token in callback.aiter():
            # Yield each token as a JSON-formatted string
            yield json.dumps({"token": token})

        # Await the completion of the generation task
        await generation_task
