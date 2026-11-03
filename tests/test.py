"""Test module for PDF-to-Podcast API functionality.

This module provides comprehensive testing capabilities for the PDF-to-Podcast API service,
including WebSocket status monitoring, file processing, and endpoint verification.
"""

import requests
import os
import json as json
import time
from datetime import datetime
from threading import Thread, Event
import websockets
import asyncio
from urllib.parse import urljoin
import argparse
from typing import List
import uuid
import random
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from pathlib import Path

# Add global TEST_USER_ID
TEST_USER_ID = "test-userid"

# Add at top of file after imports
SPEAKER_NAMES = ["Bob", "Kate", "Alex", "Sarah", "Mike"]


class StatusMonitor:
    """Monitor WebSocket status updates for PDF-to-Podcast jobs.

    This class handles WebSocket connections to track the status of PDF processing,
    agent processing, and text-to-speech conversion for a specific job.

    Attributes:
        base_url (str): Base URL of the API service
        job_id (str): Unique identifier for the job being monitored
        services (set): Set of services to monitor (pdf, agent, tts)
        tts_completed (Event): Event that is set when TTS processing completes
    """

    def __init__(self, base_url, job_id):
        """Initialize the status monitor.

        Args:
            base_url (str): Base URL of the API service
            job_id (str): Unique identifier for the job to monitor
        """
        self.base_url = base_url
        self.job_id = job_id
        self.ws_url = self._get_ws_url(base_url)
        self.stop_event = Event()
        self.services = {"pdf", "agent", "tts"}
        self.last_statuses = {service: None for service in self.services}
        self.tts_completed = Event()
        self.done = Event()
        self.error = None
        self.websocket = None
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 30.0
        self.ready_event = asyncio.Event()

    def _get_ws_url(self, base_url):
        """Convert HTTP URL to WebSocket URL"""
        if base_url.startswith("https://"):
            ws_base = "wss://" + base_url[8:]
        else:
            ws_base = "ws://" + base_url[7:]
        return urljoin(ws_base, f"/ws/status/{self.job_id}")

    def get_time(self):
        """Get current time formatted as string.

        Returns:
            str: Current time in HH:MM:SS format
        """
        return datetime.now().strftime("%H:%M:%S")

    def start(self):
        """Start the WebSocket monitoring in a separate thread"""
        self.thread = Thread(target=self._run_async_loop)
        self.thread.start()

    def stop(self):
        """Stop the WebSocket monitoring"""
        self.stop_event.set()
        self.thread.join()

    def _run_async_loop(self):
        """Run the asyncio event loop in a separate thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._monitor_status())

    async def _monitor_status(self):
        """Monitor WebSocket status updates with automatic reconnection"""
        while not self.stop_event.is_set():
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.websocket = websocket
                    self.reconnect_delay = 1.0
                    print(f"[{self.get_time()}] Connected to status WebSocket")

                    while not self.stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(), timeout=30
                            )

                            # Handle ready check message
                            try:
                                data = json.loads(message)
                                if data.get("type") == "ready_check":
                                    await websocket.send("ready")
                                    print(
                                        f"[{self.get_time()}] Sent ready acknowledgment"
                                    )
                                    continue
                            except json.JSONDecodeError:
                                pass

                            await self._handle_message(message)
                        except asyncio.TimeoutError:
                            try:
                                pong_waiter = await websocket.ping()
                                await pong_waiter
                            except Exception:
                                break

            except websockets.exceptions.ConnectionClosed:
                self.ready_event.clear()
                if not self.stop_event.is_set():
                    print(
                        f"[{self.get_time()}] WebSocket connection closed, reconnecting..."
                    )

            except Exception as e:
                self.ready_event.clear()
                if not self.stop_event.is_set():
                    print(f"[{self.get_time()}] WebSocket error: {e}, reconnecting...")

            if not self.stop_event.is_set():
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(
                    self.reconnect_delay * 1.5, self.max_reconnect_delay
                )

    async def _handle_message(self, message):
        """Handle incoming WebSocket messages.

        Args:
            message (str): JSON message from WebSocket
        """
        try:
            data = json.loads(message)
            service = data.get("service")
            status = data.get("status")
            msg = data.get("message", "")

            if service in self.services:
                current_status = f"{service}: {status} - {msg}"
                if current_status != self.last_statuses[service]:
                    print(f"[{self.get_time()}] {current_status}")
                    self.last_statuses[service] = current_status

                    if status == "failed":
                        print(f"[{self.get_time()}] Job failed in {service}: {msg}")
                        self.error = f"Job failed in {service}: {msg}"
                        self.done.set()
                        self.stop_event.set()

                    if service == "tts" and status == "completed":
                        self.tts_completed.set()
                        self.done.set()
                        self.stop_event.set()

        except json.JSONDecodeError:
            print(f"[{self.get_time()}] Received invalid JSON: {message}")
        except Exception as e:
            print(f"[{self.get_time()}] Error processing message: {e}")


def get_output_with_retry(base_url: str, job_id: str, max_retries=5, retry_delay=1):
    """Retry getting output with exponential backoff.

    Args:
        base_url (str): Base URL of the API service
        job_id (str): Job ID to get output for
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Initial delay between retries in seconds

    Returns:
        bytes: Audio file content

    Raises:
        TimeoutError: If maximum retries exceeded
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{base_url}/output/{job_id}", params={"userId": TEST_USER_ID}
            )
            if response.status_code == 200:
                return response.content
            elif response.status_code == 404:
                wait_time = retry_delay * (2**attempt)
                print(
                    f"[datetime.now().strftime('%H:%M:%S')] Output not ready yet, retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
                continue
            else:
                response.raise_for_status()
        except requests.RequestException as e:
            print(f"[datetime.now().strftime('%H:%M:%S')] Error getting output: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (2**attempt))

    raise TimeoutError("Failed to get output after maximum retries")


def test_saved_podcasts(base_url: str, job_id: str, max_retries=5, retry_delay=5):
    """Test the saved podcasts endpoints with retry logic.

    Args:
        base_url (str): Base URL of the API service
        job_id (str): Job ID to test
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Initial delay between retries in seconds

    Raises:
        AssertionError: If any endpoint tests fail
    """
    print(
        f"\n[{datetime.now().strftime('%H:%M:%S')}] Testing saved podcasts endpoints..."
    )

    # Test 1: Get all saved podcasts with retry
    print("\nTesting list all podcasts endpoint...")
    for attempt in range(max_retries):
        response = requests.get(
            f"{base_url}/saved_podcasts", params={"userId": TEST_USER_ID}
        )
        assert response.status_code == 200, (
            f"Failed to get saved podcasts: {response.text}"
        )
        podcasts = response.json()["podcasts"]
        print(f"Found {len(podcasts)} saved podcasts")

        # Check if our job_id is in the list
        job_ids = [podcast["job_id"] for podcast in podcasts]
        if job_id in job_ids:
            print(f"Successfully found job_id {job_id} in saved podcasts list")
            break
        elif attempt < max_retries - 1:
            wait_time = retry_delay * (2**attempt)
            print(
                f"Job ID not found yet, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(wait_time)
            continue
        else:
            assert False, (
                f"Recently created job_id {job_id} not found in saved podcasts after {max_retries} attempts"
            )

    # Test 2: Get specific podcast metadata
    print("\nTesting individual podcast metadata endpoint...")
    response = requests.get(
        f"{base_url}/saved_podcast/{job_id}/metadata", params={"userId": TEST_USER_ID}
    )
    assert response.status_code == 200, (
        f"Failed to get podcast metadata: {response.text}"
    )
    metadata = response.json()
    print(f"Retrieved metadata for podcast: {metadata.get('filename', 'unknown')}")
    print(f"Metadata: {json.dumps(metadata, indent=2)}")

    # Test 3: Get specific podcast audio
    print("\nTesting individual podcast audio endpoint...")
    response = requests.get(
        f"{base_url}/saved_podcast/{job_id}/audio", params={"userId": TEST_USER_ID}
    )
    assert response.status_code == 200, f"Failed to get podcast audio: {response.text}"
    audio_data = response.content
    print(f"Successfully retrieved audio data, size: {len(audio_data)} bytes")


def test_nvidia_api_key():
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY needs to be set")
    config_path = Path("./models.json")
    if config_path.exists():
        with config_path.open() as f:
            configs = json.load(f)
    else:
        raise ValueError(f"model config at path {config_path} does not exist")

    for model_type in ["reasoning", "json", "iteration"]:
        model = configs[model_type]
        llm = ChatNVIDIA(
            model=model["name"],
            base_url=model["api_base"],
            nvidia_api_key=api_key,
            max_tokens=100,
        )
        response = llm.invoke(
            [
                {
                    "role": "user",
                    "content": "What is the capital of France? Be brief",
                }
            ],
        )
        if "paris" not in response.content.lower():
            print(f"Response {response.content} did not contain expected answer Paris")

    print("Successfully validated all models with NVIDIA_API_KEY")


def test_api(
    base_url: str,
    name: str,
    target_files: List[str],
    context_files: List[str],
    speaker_1_name: str = None,
    speaker_2_name: str = None,
    monologue: bool = False,
    vdb: bool = False,
):
    """Test the PDF-to-Podcast API functionality.

    Args:
        base_url (str): Base URL of the API service
        target_files (List[str]): List of target PDF files to process
        context_files (List[str]): List of context PDF files
        monologue (bool): Whether to generate monologue instead of dialogue
        vdb (bool): Whether to enable vector database processing

    Raises:
        AssertionError: If any API tests fail
        Exception: For other errors during testing
    """
    voice_mapping = {
        "speaker-1": "iP95p4xoKVk53GoZ742B",
    }

    if not monologue:
        voice_mapping["speaker-2"] = "9BWtsMINqrJLrRacOk9x"

    # Get random names if not provided
    if speaker_1_name is None:
        speaker_1_name = random.choice(SPEAKER_NAMES)
    if speaker_2_name is None and not monologue:
        # Ensure second speaker is different from first
        available_names = [name for name in SPEAKER_NAMES if name != speaker_1_name]
        speaker_2_name = random.choice(available_names)

    # Update transcription params
    transcription_params = {
        "name": name,
        "duration": 5,
        "speaker_1_name": speaker_1_name,
        "voice_mapping": voice_mapping,
        "guide": None,
        "monologue": monologue,
        "userId": TEST_USER_ID,
        "vdb_task": vdb,
    }

    if not monologue:
        transcription_params["speaker_2_name"] = speaker_2_name

    process_url = f"{base_url}/process_pdf"

    # Update path resolution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    samples_dir = os.path.join(project_root, "samples")

    print(
        f"\n[{datetime.now().strftime('%H:%M:%S')}] Submitting PDFs for processing..."
    )
    print(f"Using voices: {voice_mapping}")

    # Prepare multipart form data
    form_data = []

    # Process target files
    for pdf_file in target_files:
        if not os.path.isabs(pdf_file):
            pdf_file = os.path.join(samples_dir, pdf_file)

        with open(pdf_file, "rb") as f:
            content = f.read()
            form_data.append(
                (
                    "target_files",
                    (os.path.basename(pdf_file), content, "application/pdf"),
                )
            )

    # Process context files
    for pdf_file in context_files:
        if not os.path.isabs(pdf_file):
            pdf_file = os.path.join(samples_dir, pdf_file)

        with open(pdf_file, "rb") as f:
            content = f.read()
            form_data.append(
                (
                    "context_files",
                    (os.path.basename(pdf_file), content, "application/pdf"),
                )
            )

    # Add transcription parameters
    form_data.append(("transcription_params", (None, json.dumps(transcription_params))))

    try:
        response = requests.post(process_url, files=form_data)

        assert response.status_code == 202, (
            f"Expected status code 202, but got {response.status_code}. Response: {response.text}"
        )
        job_data = response.json()
        assert "job_id" in job_data, "Response missing job_id"
        job_id = job_data["job_id"]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Job ID received: {job_id}")

        # Step 2: Start monitoring status via WebSocket
        monitor = StatusMonitor(base_url, job_id)
        monitor.start()

        try:
            # Wait for TTS completion, a failed service, or timeout
            max_wait = 40 * 60
            if not monitor.done.wait(timeout=max_wait):
                raise TimeoutError(f"Test timed out after {max_wait} seconds")
            if monitor.error:
                raise RuntimeError(monitor.error)

            # If we get here, TTS completed successfully
            print(
                f"\n[{datetime.now().strftime('%H:%M:%S')}] TTS processing completed, retrieving audio file..."
            )

            # Get the final output with retry logic
            audio_content = get_output_with_retry(base_url, job_id)

            # Save the audio file
            output_path = os.path.join(current_dir, f"{name}.mp3")
            with open(output_path, "wb") as f:
                f.write(audio_content)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] Audio file saved as '{output_path}'"
            )

            # Test saved podcasts endpoints with the newly created job_id
            test_saved_podcasts(base_url, job_id)

            # Test RAG endpoint if vdb flag is enabled
            if vdb:
                print("\nTesting RAG endpoint...")
                test_query = "What is the main topic of this document?"
                rag_response = requests.post(
                    f"{base_url}/query_vector_db",
                    json={"query": test_query, "k": 3, "job_id": job_id},
                )
                assert rag_response.status_code == 200, (
                    f"RAG endpoint failed: {rag_response.text}"
                )
                rag_results = rag_response.json()
                print(f"RAG Query: '{test_query}'")
                print(f"RAG Results: {json.dumps(rag_results, indent=2)}")

        finally:
            monitor.stop()

    except Exception as e:
        print(f"Error during PDF submission: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process PDF files for audio conversion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        # Process with target and context files
        python test.py --target main.pdf --context context1.pdf context2.pdf

        # Process with only context files
        python test.py --context file1.pdf file2.pdf file3.pdf

        # Process with multiple target files
        python test.py --target target1.pdf target2.pdf --context context1.pdf
        """,
    )
    parser.add_argument(
        "--name",
        default=str(uuid.uuid4()),
        help="Name of the generated podcast",
    )
    parser.add_argument(
        "--target",
        nargs="+",
        default=[],
        help="PDF files to use as targets",
        metavar="PDF",
    )
    parser.add_argument(
        "--context",
        nargs="+",
        default=[],
        help="PDF files to use as context",
        metavar="PDF",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("API_SERVICE_URL", "http://localhost:8002"),
        help="API service URL (default: from API_SERVICE_URL env var or http://localhost:8002)",
    )
    parser.add_argument(
        "--monologue",
        action="store_true",
        help="Generate a monologue instead of a dialogue",
    )
    parser.add_argument(
        "--vdb",
        action="store_true",
        help="Enable Vector Database processing",
    )
    parser.add_argument(
        "--speaker1",
        help=f"Name for speaker 1 (default: random from {SPEAKER_NAMES})",
    )
    parser.add_argument(
        "--speaker2",
        help=f"Name for speaker 2 (default: random from {SPEAKER_NAMES})",
    )

    args = parser.parse_args()

    # Validate that at least one file was provided
    if not args.target and not args.context:
        parser.error(
            "At least one PDF file must be provided (either target or context)"
        )

    print(f"API URL: {args.api_url}")
    print(f"Target PDF files: {args.target}")
    print(f"Context PDF files: {args.context}")
    print(f"Monologue mode: {args.monologue}")
    print(f"VDB mode: {args.vdb}")
    print(f"Using test user ID: {TEST_USER_ID}")

    test_nvidia_api_key()

    test_api(
        args.api_url,
        args.name,
        args.target,
        args.context,
        speaker_1_name=args.speaker1,
        speaker_2_name=args.speaker2,
        monologue=args.monologue,
        vdb=args.vdb,
    )
