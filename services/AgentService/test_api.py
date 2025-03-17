"""
Test module for the Agent Service API endpoints.

This module contains integration tests for the transcription API endpoints,
verifying the full workflow from request submission to job completion.
"""

import requests
import ujson as json
import os
import time
from shared.api_types import TranscriptionRequest
from shared.pdf_types import PDFMetadata


def test_transcribe_api():
    """
    Test the transcription API workflow.
    
    This test function:
    1. Creates a TranscriptionRequest with sample PDF metadata
    2. Submits the request to the transcribe endpoint
    3. Polls the job status until completion
    4. Verifies the job completes successfully
    
    Raises:
        AssertionError: If any step of the workflow fails or times out
    """
    # API endpoints
    BASE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8964")
    TRANSCRIBE_URL = f"{BASE_URL}/transcribe"

    # Create a proper TranscriptionRequest
    pdf_metadata_1 = PDFMetadata(
        filename="sample.pdf", markdown="Sample markdown content", summary=""
    )

    pdf_metadata_2 = PDFMetadata(
        filename="sample2.pdf", markdown="Sample markdown content 2", summary=""
    )

    pdf_metadata_3 = PDFMetadata(
        filename="sample3.pdf", markdown="Sample markdown content 3", summary=""
    )

    request = TranscriptionRequest(
        # TranscriptionParams fields
        name="Test Podcast",
        duration=2,  # Duration in minutes
        speaker_1_name="Host",
        speaker_2_name="Guest",
        voice_mapping={
            "speaker-1": "iP95p4xoKVk53GoZ742B",  # Example voice ID
            "speaker-2": "9BWtsMINqrJLrRacOk9x",  # Example voice ID
        },
        guide="Sample focus instructions",  # Optional
        # TranscriptionRequest specific fields
        pdf_metadata=[pdf_metadata_1, pdf_metadata_2, pdf_metadata_3],
        job_id="test-job-123",
    )

    # Send POST request
    response = requests.post(TRANSCRIBE_URL, json=request.model_dump())

    # Check if the request was successful
    assert (
        response.status_code == 202
    ), f"Expected status code 202, but got {response.status_code}. Response: {response.text}"

    # Parse the JSON response
    try:
        result = response.json()
        assert "job_id" in result, "Response should contain job_id"
        job_id = result["job_id"]
        print(f"Job created with ID: {job_id}")
    except json.JSONDecodeError:
        assert False, "Response is not valid JSON"

    # Poll the job status until completion or timeout
    MAX_WAIT_TIME = 600  # 10 minutes timeout
    POLL_INTERVAL = 10  # Check every 5 seconds
    start_time = time.time()

    print("\nWaiting for job to complete...")
    while time.time() - start_time < MAX_WAIT_TIME:
        try:
            status_response = requests.get(f"{BASE_URL}/status/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data.get("status")
                message = status_data.get("message", "No message")
                print(f"Status: {status} - {message}")

                if status == "COMPLETED":
                    print("\nJob completed successfully!")
                    return
                elif status == "FAILED":
                    assert False, f"Job failed: {message}"

            time.sleep(POLL_INTERVAL)
        except Exception as e:
            print(f"Error checking status: {e}")
            time.sleep(POLL_INTERVAL)

    assert False, f"Job did not complete within {MAX_WAIT_TIME} seconds"


def test_approve_pr():
    """
    Test the manual PR approval functionality.
    
    This test function:
    1. Sets up a mock PR number
    2. Runs the `make approve-pr` command with the mock PR number
    3. Verifies the command executes successfully
    
    Raises:
        AssertionError: If the command execution fails
    """
    # Mock PR number
    pr_number = "123"

    # Run the `make approve-pr` command
    result = os.system(f"make approve-pr PR_NUMBER={pr_number}")

    # Check if the command executed successfully
    assert result == 0, f"Expected command to execute successfully, but got {result}"


if __name__ == "__main__":
    test_transcribe_api()
    test_approve_pr()
    print("All tests passed!")
