from langchain_nvidia_ai_endpoints import ChatNVIDIA
from typing import List, Dict, Any, Optional, Union
import logging
import ujson as json
from shared.otel import OpenTelemetryInstrumentation
from opentelemetry.trace.status import StatusCode
from pathlib import Path
from dataclasses import dataclass
from langchain_core.messages import AIMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a specific LLM model.
    
    Attributes:
        name (str): Name/identifier of the model
        api_base (str): Base URL for the model's API endpoint
    """
    name: str
    api_base: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """Create a ModelConfig instance from a dictionary.
        
        Args:
            data (Dict[str, Any]): Dictionary containing model configuration
            
        Returns:
            ModelConfig: New ModelConfig instance
        """
        return cls(
            name=data["name"],
            api_base=data["api_base"],
        )


class LLMManager:
    """
    A lightweight and user friendly wrapper over Langchain's ChatNVIDIA class. We use this class
    to abstract away all Langchain functionalities including models, async/sync queries,
    structured outputs, types, streaming and more. It also comes with OTEL telemetry out of the box
    for all queries. It is specifically tailored for singular invocations.

    Configs can be overridden by providing a custom config file. Currently the defaults are
    hardcoded to build.nvidia.com endpoints.

    Attributes:
        api_key (str): API key for NVIDIA endpoints
        telemetry (OpenTelemetryInstrumentation): Telemetry instrumentation instance
        _llm_cache (Dict[str, ChatNVIDIA]): Cache of initialized LLM models
        model_configs (Dict[str, ModelConfig]): Model configurations

    Usage:
    >>> llm_manager = LLMManager(api_key, telemetry)
    >>> llm_manager.query_sync("reasoning", [{"role": "user", "content": "Hello, world!"}], "test")
    """

    DEFAULT_CONFIGS = {
        "reasoning": {
            "name": "meta/llama-3.1-405b-instruct",
            "api_base": "https://integrate.api.nvidia.com/v1",
        },
        "iteration": {
            "name": "meta/llama-3.1-405b-instruct",
            "api_base": "https://integrate.api.nvidia.com/v1",
        },
        "json": {
            "name": "meta/llama-3.1-70b-instruct",
            "api_base": "https://integrate.api.nvidia.com/v1",
        },
    }

    def __init__(
        self,
        api_key: str,
        telemetry: OpenTelemetryInstrumentation,
        config_path: Optional[str] = None,
    ):
        """
        Initialize LLMManager with telemetry.

        Args:
            api_key (str): API key for NVIDIA endpoints
            telemetry (OpenTelemetryInstrumentation): Telemetry instrumentation instance
            config_path (Optional[str]): Path to custom model configurations file

        Raises:
            Exception: If initialization fails
        """
        try:
            self.api_key = api_key
            self.telemetry = telemetry
            self._llm_cache: Dict[str, ChatNVIDIA] = {}
            self.model_configs = self._load_configurations(config_path)
            logger.info("Successfully initialized LLMManager")
        except Exception as e:
            logger.error(f"Failed to initialize LLMManager: {e}")
            raise

    def _load_configurations(
        self, config_path: Optional[str]
    ) -> Dict[str, ModelConfig]:
        """Load model configurations from JSON file if provided, otherwise use defaults.
        
        Args:
            config_path (Optional[str]): Path to configuration JSON file
            
        Returns:
            Dict[str, ModelConfig]: Dictionary mapping model keys to configurations
        """
        configs = self.DEFAULT_CONFIGS.copy()
        if config_path:
            try:
                config_path = Path(config_path)
                if config_path.exists():
                    with config_path.open() as f:
                        custom_configs = json.load(f)
                    configs.update(custom_configs)
                else:
                    logger.warning(
                        f"Config file {config_path} not found, using default configurations"
                    )
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                logger.warning("Using default configurations")
        return {key: ModelConfig.from_dict(config) for key, config in configs.items()}

    def get_llm(self, model_key: str) -> ChatNVIDIA:
        """Get or create a ChatNVIDIA model for the specified model key.
        
        Args:
            model_key (str): Key identifying which model configuration to use
            
        Returns:
            ChatNVIDIA: Initialized ChatNVIDIA instance
            
        Raises:
            ValueError: If model_key is not found in configurations
        """
        if model_key not in self.model_configs:
            raise ValueError(f"Unknown model key: {model_key}")
        if model_key not in self._llm_cache:
            config = self.model_configs[model_key]
            self._llm_cache[model_key] = ChatNVIDIA(
                model=config.name,
                base_url=config.api_base,
                nvidia_api_key=self.api_key,
                max_tokens=None,
            )
        return self._llm_cache[model_key]

    def query_sync(
        self,
        model_key: str,
        messages: List[Dict[str, str]],
        query_name: str,
        json_schema: Optional[Dict] = None,
        retries: int = 5,
    ) -> Union[AIMessage, Dict[str, Any]]:
        """Send a synchronous query to the specified model.
        
        Args:
            model_key (str): Key identifying which model to use
            messages (List[Dict[str, str]]): List of message dictionaries
            query_name (str): Name of query for telemetry
            json_schema (Optional[Dict]): Schema for structured output
            retries (int): Number of retry attempts
            
        Returns:
            Union[AIMessage, Dict[str, Any]]: Model response
            
        Raises:
            Exception: If query fails after retries
        """
        with self.telemetry.tracer.start_as_current_span(
            f"agent.query.{query_name}"
        ) as span:
            span.set_attribute("model_key", model_key)
            span.set_attribute("retries", retries)
            span.set_attribute("async", False)

            try:
                llm = self.get_llm(model_key)
                if json_schema:
                    llm = llm.with_structured_output(json_schema)
                llm = llm.with_retry(
                    stop_after_attempt=retries, wait_exponential_jitter=True
                )
                resp = llm.invoke(messages)
                return resp
            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(f"Query failed: {e}")
                raise Exception(
                    f"Failed to get response after {retries} attempts"
                ) from e

    async def query_async(
        self,
        model_key: str,
        messages: List[Dict[str, str]],
        query_name: str,
        json_schema: Optional[Dict] = None,
        retries: int = 5,
    ) -> Union[AIMessage, Dict[str, Any]]:
        """Send an asynchronous query to the specified model.
        
        Args:
            model_key (str): Key identifying which model to use
            messages (List[Dict[str, str]]): List of message dictionaries
            query_name (str): Name of query for telemetry
            json_schema (Optional[Dict]): Schema for structured output
            retries (int): Number of retry attempts
            
        Returns:
            Union[AIMessage, Dict[str, Any]]: Model response
            
        Raises:
            Exception: If query fails after retries
        """
        with self.telemetry.tracer.start_as_current_span(
            f"agent.query.{query_name}"
        ) as span:
            span.set_attribute("model_key", model_key)
            span.set_attribute("retries", retries)
            span.set_attribute("async", True)

            try:
                llm = self.get_llm(model_key)
                if json_schema:
                    llm = llm.with_structured_output(json_schema)
                llm = llm.with_retry(
                    stop_after_attempt=retries, wait_exponential_jitter=True
                )
                resp = await llm.ainvoke(messages)
                return resp
            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(f"Query failed: {e}")
                raise Exception(
                    f"Failed to get response after {retries} attempts"
                ) from e

    def stream_sync(
        self,
        model_key: str,
        messages: List[Dict[str, str]],
        query_name: str,
        json_schema: Optional[Dict] = None,
        retries: int = 5,
    ) -> Union[str, Dict[str, Any]]:
        """Send a synchronous streaming query to the specified model.
        
        Args:
            model_key (str): Key identifying which model to use
            messages (List[Dict[str, str]]): List of message dictionaries
            query_name (str): Name of query for telemetry
            json_schema (Optional[Dict]): Schema for structured output
            retries (int): Number of retry attempts
            
        Returns:
            Union[str, Dict[str, Any]]: Final chunk from model stream
            
        Raises:
            Exception: If streaming query fails after retries
        """
        with self.telemetry.tracer.start_as_current_span(
            f"agent.stream.{query_name}"
        ) as span:
            span.set_attribute("model_key", model_key)
            span.set_attribute("retries", retries)
            span.set_attribute("async", False)

            try:
                llm = self.get_llm(model_key)
                if json_schema:
                    llm = llm.with_structured_output(json_schema)
                llm = llm.with_retry(
                    stop_after_attempt=retries, wait_exponential_jitter=True
                )

                last_chunk = None
                for chunk in llm.stream(messages):
                    # AIMessage returns content and JSON returns the dict itself
                    if hasattr(chunk, "content"):
                        last_chunk = chunk.content
                    else:
                        last_chunk = chunk

                return last_chunk

            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(f"Streaming query failed: {e}")
                raise Exception(
                    f"Failed to get streaming response after {retries} attempts"
                ) from e

    async def stream_async(
        self,
        model_key: str,
        messages: List[Dict[str, str]],
        query_name: str,
        json_schema: Optional[Dict] = None,
        retries: int = 5,
    ) -> Union[str, Dict[str, Any]]:
        """Send an asynchronous streaming query to the specified model.
        
        Args:
            model_key (str): Key identifying which model to use
            messages (List[Dict[str, str]]): List of message dictionaries
            query_name (str): Name of query for telemetry
            json_schema (Optional[Dict]): Schema for structured output
            retries (int): Number of retry attempts
            
        Returns:
            Union[str, Dict[str, Any]]: Final chunk from model stream
            
        Raises:
            Exception: If streaming query fails after retries
        """
        with self.telemetry.tracer.start_as_current_span(
            f"agent.stream.{query_name}"
        ) as span:
            span.set_attribute("model_key", model_key)
            span.set_attribute("retries", retries)
            span.set_attribute("async", True)

            try:
                llm = self.get_llm(model_key)
                if json_schema:
                    llm = llm.with_structured_output(json_schema)
                llm = llm.with_retry(
                    stop_after_attempt=retries, wait_exponential_jitter=True
                )

                last_chunk = None
                async for chunk in llm.astream(messages):
                    # AIMessage returns content and JSON returns the dict itself
                    if hasattr(chunk, "content"):
                        last_chunk = chunk.content
                    else:
                        last_chunk = chunk

                return last_chunk

            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(f"Async streaming query failed: {e}")
                raise Exception(
                    f"Failed to get streaming response after {retries} attempts"
                ) from e
