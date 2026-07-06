"""Setup script for the shared package.

This package contains shared utilities and functionality used across the pdf-to-podcast
application, including storage management, telemetry, and type definitions.

The package requires several external dependencies for Redis caching, HTTP requests,
data validation, and AI model integration.
"""

from setuptools import setup, find_packages

setup(
    name="shared",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "redis",  # For caching and message queuing
        "pydantic",  # For data validation and serialization
        "httpx",  # For async HTTP requests
        "requests",  # For sync HTTP requests
        "langchain-nvidia-ai-endpoints",  # For remote NIM endpoints
        "langchain-openai",  # XPU: for local vLLM-XPU / SGLang-XPU OpenAI-compatible endpoints
    ],
)
