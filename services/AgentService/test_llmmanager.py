"""
Test module for the LLMManager class.

This module contains integration tests for the LLMManager class, testing various
capabilities like basic queries, parallel processing, JSON schema validation,
and streaming responses. It uses a mock FastAPI application and OpenTelemetry
instrumentation for testing purposes.
"""

import asyncio
import os
from shared.otel import OpenTelemetryInstrumentation, OpenTelemetryConfig
import logging
from fastapi import FastAPI
from shared.llmmanager import LLMManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up mock FastAPI app and telemetry for testing
mock_app = FastAPI()
mock_telemetry = OpenTelemetryInstrumentation()
mock_config = OpenTelemetryConfig(
    service_name="test-llm-manager",
    otlp_endpoint="",
    enable_redis=False,
    enable_requests=False,
)
mock_telemetry.initialize(mock_config, mock_app)


async def test_basic_queries():
    """
    Test both synchronous and asynchronous basic queries.
    
    Tests the basic query functionality of LLMManager by making both sync
    and async requests with simple prompts. Verifies that both methods
    return expected responses.
    """
    print("\n=== Testing Basic Queries ===")

    manager = LLMManager(api_key=os.getenv("NVIDIA_API_KEY"), telemetry=mock_telemetry)

    # Test sync query
    print("\nTesting sync query...")
    response = manager.query_sync(
        model_key="reasoning",
        messages=[
            {
                "role": "user",
                "content": "What are the three laws of robotics? Be brief.",
            }
        ],
        query_name="test_sync",
    )
    print(f"Sync Response: {response}\n")

    # Test async query
    print("Testing async query...")
    response = await manager.query_async(
        model_key="reasoning",
        messages=[
            {
                "role": "user",
                "content": "What is machine learning? Answer in one sentence.",
            }
        ],
        query_name="test_async",
    )
    print(f"Async Response: {response}\n")


async def test_parallel_processing():
    """
    Test processing multiple queries in parallel.
    
    Demonstrates the ability to process multiple queries concurrently using
    asyncio.gather(). Sends three different programming language queries
    simultaneously and collects their responses.
    """
    print("\n=== Testing Parallel Processing ===")

    manager = LLMManager(api_key=os.getenv("NVIDIA_API_KEY"), telemetry=mock_telemetry)

    questions = ["What is Python?", "What is JavaScript?", "What is Rust?"]

    async def process_query(question: str, idx: int):
        return await manager.query_async(
            model_key="reasoning",
            messages=[
                {"role": "user", "content": f"Explain {question} in one sentence."}
            ],
            query_name=f"test_parallel_{idx}",
        )

    print("\nSending parallel queries...")
    tasks = [process_query(q, i) for i, q in enumerate(questions)]
    responses = await asyncio.gather(*tasks)

    for question, response in zip(questions, responses):
        print(f"\nQuestion: {question}")
        print(f"Response: {response}")


async def test_json_schema():
    """
    Test JSON schema structured output.
    
    Verifies that the LLMManager can generate responses conforming to a
    specified JSON schema. Uses a sample schema for person details including
    name, age, occupation, and hobbies.
    """
    print("\n=== Testing JSON Schema ===")

    manager = LLMManager(api_key=os.getenv("NVIDIA_API_KEY"), telemetry=mock_telemetry)

    # Define a schema for a person's details
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "occupation": {"type": "string"},
            "hobbies": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "age", "occupation", "hobbies"],
    }

    print("\nTesting structured output...")
    response = manager.query_sync(
        model_key="json",
        messages=[
            {"role": "user", "content": "Generate details for a fictional character."}
        ],
        query_name="test_json",
        json_schema=schema,
    )
    print(f"Structured Response: {response}")


async def test_streaming():
    """
    Test both synchronous and asynchronous streaming.
    
    Tests the streaming capabilities of LLMManager using both sync and async
    methods. Verifies that streaming responses are received correctly for
    simple counting and listing tasks.
    """
    print("\n=== Testing Streaming ===")

    manager = LLMManager(api_key=os.getenv("NVIDIA_API_KEY"), telemetry=mock_telemetry)

    # Test sync streaming
    print("\nTesting sync streaming...")
    response = manager.stream_sync(
        model_key="reasoning",
        messages=[
            {
                "role": "user",
                "content": "Count from 1 to 5 slowly.",
            }
        ],
        query_name="test_stream_sync",
    )
    print(f"Sync Streaming Response: {response}\n")

    # Test async streaming
    print("Testing async streaming...")
    response = await manager.stream_async(
        model_key="reasoning",
        messages=[
            {
                "role": "user",
                "content": "List the days of the week one by one.",
            }
        ],
        query_name="test_stream_async",
    )
    print(f"Async Streaming Response: {response}\n")


async def test_json_streaming():
    """
    Test JSON schema structured output with streaming.
    
    Tests the combination of JSON schema validation and streaming responses.
    Uses a simple story summary schema to verify that streamed responses
    conform to the specified structure.
    """
    print("\n=== Testing JSON Streaming ===")

    manager = LLMManager(api_key=os.getenv("NVIDIA_API_KEY"), telemetry=mock_telemetry)

    # Define a simpler schema
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "rating": {"type": "integer"},
        },
        "required": ["title", "summary", "rating"],
    }

    # Test sync streaming with JSON
    print("\nTesting sync JSON streaming...")
    response = manager.stream_sync(
        model_key="json",
        messages=[
            {
                "role": "user",
                "content": "Create a brief story summary with a rating.",
            }
        ],
        query_name="test_json_stream_sync",
        json_schema=schema,
    )
    print(f"Sync JSON Streaming Response: {response}\n")

    # Test async streaming with JSON
    print("Testing async JSON streaming...")
    response = await manager.stream_async(
        model_key="json",
        messages=[
            {
                "role": "user",
                "content": "Create a brief 3 sentence story outline about a medieval quest.",
            }
        ],
        query_name="test_json_stream_async",
        json_schema=schema,
    )
    print(f"Async JSON Streaming Response: {response}\n")


async def main_test():
    """
    Run all tests sequentially.
    
    Main test runner that executes all test functions in sequence.
    Currently configured to run only streaming tests, with other tests
    commented out for focused testing.
    """
    try:
        # # Test basic queries
        # await test_basic_queries()

        # # Test parallel processing
        # await test_parallel_processing()

        # # Test JSON schema
        # await test_json_schema()

        # Test streaming
        await test_streaming()

        # Test JSON streaming
        await test_json_streaming()

    except Exception as e:
        print(f"\nError occurred: {str(e)}")


if __name__ == "__main__":
    # Ensure NVIDIA_API_KEY is set
    if not os.getenv("NVIDIA_API_KEY"):
        print("Error: NVIDIA_API_KEY environment variable not set")
    else:
        asyncio.run(main_test())
