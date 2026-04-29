"""Test module for invalid file type handling.

This module contains test functions to verify that the API properly handles
invalid file types and malformed transcription parameters.
"""

import os
import requests
from requests import Response
import ujson as json
from datetime import datetime


def test(base_url: str):
    """Test invalid file type and parameter handling.
    
    Tests two scenarios:
    1. Submitting a .txt file instead of PDF
    2. Submitting invalid transcription parameters
    
    Args:
        base_url (str): Base URL of the API service
    
    Raises:
        AssertionError: If response status codes don't match expected 400
    """
    # Define default voice mapping
    voice_mapping = {
        "speaker-1": "iP95p4xoKVk53GoZ742B",  # Example voice ID for speaker 1
        "speaker-2": "9BWtsMINqrJLrRacOk9x",  # Example voice ID for speaker 2
    }

    # Prepare the payload
    transcription_params = {
        "name": "ishan-test",
        "duration": 5,
        "speaker_1_name": "Blackwell",
        "speaker_2_name": "Hopper",
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "voice_mapping": voice_mapping,  # Add voice mapping
    }

    response = test_api(base_url, "PNP_Proof.txt", "text/plain", transcription_params)

    assert (
        response.status_code == 400
    ), f"Expected status code 400, but got {response.status_code}"

    transcription_params = {
        "test": "test",
    }
    response = test_api(
        base_url, "PNP_Proof.pdf", "application/pdf", transcription_params
    )

    assert (
        response.status_code == 400
    ), f"Expected status code 400, but got {response.status_code}"


def test_api(
    base_url: str, file_name: str, file_type: str, transcription_params: dict[str, any]
) -> Response:
    """Test the PDF processing API endpoint with various inputs.

    Args:
        base_url (str): Base URL of the API service
        file_name (str): Name of the file to upload
        file_type (str): MIME type of the file
        transcription_params (dict[str, any]): Parameters for transcription

    Returns:
        Response: Response object from the API request

    Raises:
        FileNotFoundError: If samples directory or test file not found
        AssertionError: If test file does not exist
    """
    # API endpoint
    process_url = f"{base_url}/process_pdf"

    # Path to a sample PDF file for testing
    current_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(current_dir, "samples")

    # Ensure samples directory exists
    if not os.path.exists(samples_dir):
        raise FileNotFoundError(f"Samples directory not found at {samples_dir}")

    sample_pdf_path = os.path.join(samples_dir, file_name)

    # Ensure the sample PDF file exists
    assert os.path.exists(
        sample_pdf_path
    ), f"Sample PDF file not found at {sample_pdf_path}"

    # Step 1: Submit the PDF file and get job ID
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Submitting PDF for processing...")

    with open(sample_pdf_path, "rb") as file:
        files = {"file": (file_name, file, file_type)}
        response = requests.post(
            process_url,
            files=files,
            data={"transcription_params": json.dumps(transcription_params)},
        )

    return response


if __name__ == "__main__":
    base_url = os.getenv("API_SERVICE_URL", "http://localhost:8002")
    print(f"{base_url=}")
    test(base_url)
