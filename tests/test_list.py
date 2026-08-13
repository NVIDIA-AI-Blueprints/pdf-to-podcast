"""Test module for listing saved podcasts.

This module provides functionality to retrieve and display a list of all saved podcasts
from the PDF-to-Podcast API service, including their metadata and transcription parameters.
"""
import os

import requests
import ujson as json
from datetime import datetime


def format_timestamp(timestamp_str: str) -> str:
    """Format an ISO timestamp string into a more readable format.
    
    Args:
        timestamp_str (str): ISO format timestamp string with timezone info
        
    Returns:
        str: Formatted timestamp string in the format "Month DD, YYYY at HH:MM AM/PM"
    """
    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    return dt.strftime("%B %d, %Y at %I:%M %p")


def list_saved_podcasts():
    """Retrieve and display a list of all saved podcasts from the API.
    
    Makes a GET request to the /saved_podcasts endpoint and prints details of each podcast
    including:
    - Job ID
    - Filename
    - Creation timestamp
    - Transcription parameters
    
    Handles various error cases like connection failures and invalid responses.
    
    Environment Variables:
        API_SERVICE_URL: Base URL of the API service (default: http://localhost:8002)
    """
    try:
        base_url = os.getenv("API_SERVICE_URL", "http://localhost:8002").rstrip("/")
        endpoint = f"{base_url}/saved_podcasts"
        print(f"\nAttempting to connect to API at {base_url}...")
        response = requests.get(endpoint)
        response.raise_for_status()

        data = response.json()
        podcasts = data.get("podcasts", [])

        if not podcasts:
            print("\nNo saved podcasts found in API response.")

        print("\nSaved Podcasts:")
        print("-" * 80)

        for podcast in podcasts:
            created_at = format_timestamp(podcast["created_at"])
            print(f"Job ID: {podcast['job_id']}")
            print(f"Filename: {podcast['filename']}")
            print(f"Created: {created_at}")
            print("Transcription Parameters:")
            print(json.dumps(podcast["transcription_params"], indent=2))
            print("-" * 80)

        print(f"\nTotal podcasts found: {len(podcasts)}")

    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API service. Is it running?")
    except requests.exceptions.HTTPError as e:
        print(f"Error: API request failed with status {e.response.status_code}")
        print(f"Details: {e.response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    list_saved_podcasts()
