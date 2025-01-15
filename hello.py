import requests
import json
import time
from typing import List
from pathlib import Path

BASE_URL = "http://localhost:8002"

def generate_podcast(
    target_pdf_paths: List[str], 
    name: str,
    duration: int,
    speaker_1_name: str,
    context_pdf_paths: List[str] = None,
    is_monologue: bool = False,
    speaker_2_name: str = None,
    guide: str = None
) -> str:
    """
    Generate a podcast using the API.
    
    Args:
        target_pdf_paths: List of paths to main PDFs to analyze
        name: Name of the podcast
        duration: Desired duration in minutes
        speaker_1_name: Name of the first speaker
        context_pdf_paths: Optional list of paths to context PDFs
        is_monologue: Whether to generate a monologue
        speaker_2_name: Name of second speaker (required if not monologue)
        guide: Optional guidance for the podcast structure
    """
    # Handle single path inputs
    if isinstance(target_pdf_paths, str):
        target_pdf_paths = [target_pdf_paths]
    if isinstance(context_pdf_paths, str):
        context_pdf_paths = [context_pdf_paths]
    
    files = []
    
    # Add all target PDFs
    for pdf_path in target_pdf_paths:
        content = Path(pdf_path).read_bytes()
        files.append(('target_files', (Path(pdf_path).name, content, 'application/pdf')))
    
    # Add all context PDFs if provided
    if context_pdf_paths:
        for pdf_path in context_pdf_paths:
            content = Path(pdf_path).read_bytes()
            files.append(('context_files', (Path(pdf_path).name, content, 'application/pdf')))
    
    # Configure voice mapping
    voice_mapping = {
        "speaker-1": "iP95p4xoKVk53GoZ742B" 
    }
    if not is_monologue:
        voice_mapping["speaker-2"] = "9BWtsMINqrJLrRacOk9x"
    
    # Create parameters
    params = {
        "userId": "test-userid",
        "name": name,
        "duration": duration,
        "monologue": is_monologue,
        "speaker_1_name": speaker_1_name,
        "voice_mapping": voice_mapping,
        "guide": guide,
        "vdb_task": False
    }
    if not is_monologue:
        params["speaker_2_name"] = speaker_2_name
    
    response = requests.post(
        f"{BASE_URL}/process_pdf", 
        files=files,
        data={'transcription_params': json.dumps(params)}
    )
    if response.status_code != 202:
        raise Exception(f"Failed to submit podcast generation: {response.text}")
    
    return response.json()['job_id']

def get_status(job_id: str) -> dict:
    """Get the current status of all services for a job."""
    response = requests.get(f"{BASE_URL}/status/{job_id}?userId=test-userid")
    if response.status_code != 200:
        raise Exception(f"Failed to get status: {response.text}")
    return response.json()

def wait_for_completion(job_id: str, check_interval: int = 5, initial_delay: int = 1):
    """
    Poll the status endpoint until the podcast is ready.
    Shows a simplified progress view.
    """
    print(f"Waiting {initial_delay} seconds for job to initialize...")
    time.sleep(initial_delay)
    
    last_messages = {}  # Track last message for each service to avoid duplication
    
    while True:
        try:
            statuses = get_status(job_id)
            
            # Check each service and only print if status changed
            for service, status in statuses.items():
                current_msg = status.get('message', '')
                if current_msg != last_messages.get(service):
                    print(f"[{service.upper()}] {current_msg}")
                    last_messages[service] = current_msg
            
            # Check if everything is completed
            all_completed = all(
                status.get('status') == 'JobStatus.COMPLETED' 
                for status in statuses.values()
            )
            
            if all_completed and 'tts' in statuses:
                print("\nPodcast generation completed!")
                return
            
            # Check for failures
            for service, status in statuses.items():
                if status.get('status') == 'JobStatus.FAILED':
                    raise Exception(f"Service {service} failed: {status.get('message')}")
            
            time.sleep(check_interval)
            
        except requests.exceptions.RequestException as e:
            if "Job not found" in str(e):
                print("Waiting for job to start...")
                time.sleep(check_interval)
                continue
            raise
        except Exception as e:
            print(f"Error: {e}")
            raise

def main(): 
    job_id=generate_podcast(
        target_pdf_paths=[Path().joinpath("samples", "investorpres-main.pdf").resolve()], 
        duration=2,
        speaker_1_name="sean",
        speaker_2_name="jerk",
        name="nobody_wants_this"
    )
    wait_for_completion(job_id)

if __name__ == "__main__":
    main()
