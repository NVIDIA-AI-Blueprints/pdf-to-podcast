import os
import io
import time
from minio import Minio
from datetime import datetime
from dataclasses import dataclass
from typing import Dict


# Mock the TranscriptionParams that was in main.py
@dataclass
class TranscriptionParams:
    """Parameters for transcription configuration.

    Attributes:
        name (str): Name of the podcast
        duration (int): Duration in minutes
        speaker_1_name (str): Name of first speaker
        speaker_2_name (str): Name of second speaker
        model (str): Model to use for transcription
        voice_mapping (Dict[str, str]): Mapping of speaker IDs to voice IDs
    """
    name: str
    duration: int
    speaker_1_name: str
    speaker_2_name: str
    model: str
    voice_mapping: Dict[str, str]


class StorageManager:
    """Manages storage operations with MinIO for audio files.

    This class handles initialization of MinIO client, bucket creation,
    and operations for storing and retrieving audio files.
    """

    def __init__(self):
        """Initialize MinIO client and ensure bucket exists.

        Raises:
            Exception: If MinIO client initialization fails
        """
        try:
            self.client = Minio(
                os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
                secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            )

            self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "audio-results")
            self._ensure_bucket_exists()
            print(f"[{self.get_time()}] Successfully initialized MinIO storage")

        except Exception as e:
            print(f"[{self.get_time()}] Failed to initialize MinIO client: {e}")
            raise

    def get_time(self):
        """Get current time formatted as string.

        Returns:
            str: Current time in HH:MM:SS format
        """
        return datetime.now().strftime("%H:%M:%S")

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist.

        Raises:
            Exception: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"[{self.get_time()}] Created bucket: {self.bucket_name}")
        except Exception as e:
            print(f"[{self.get_time()}] Failed to ensure bucket exists: {e}")
            raise

    def store_audio(
        self,
        job_id: str,
        audio_content: bytes,
        filename: str,
        transcription_params: TranscriptionParams,
    ):
        """Store audio file in MinIO.

        Args:
            job_id (str): Unique identifier for the job
            audio_content (bytes): Audio file content
            filename (str): Name of the audio file
            transcription_params (TranscriptionParams): Parameters for transcription

        Returns:
            bool: True if storage successful, False otherwise
        """
        try:
            object_name = f"{job_id}/{filename}"
            self.client.put_object(
                self.bucket_name,
                object_name,
                io.BytesIO(audio_content),
                len(audio_content),
                content_type="audio/mpeg",
            )
            print(
                f"[{self.get_time()}] Stored audio for {job_id} in MinIO as {object_name}"
            )
            return True
        except Exception as e:
            print(f"[{self.get_time()}] Failed to store audio in MinIO: {e}")
            return False

    def get_audio(self, job_id: str, filename: str):
        """Retrieve audio file from MinIO.

        Args:
            job_id (str): Unique identifier for the job
            filename (str): Name of the audio file

        Returns:
            bytes: Audio file content if successful, None otherwise
        """
        try:
            object_name = f"{job_id}/{filename}"
            response = self.client.get_object(self.bucket_name, object_name)
            try:
                result = response.read()
            finally:
                response.close()
            print(
                f"[{self.get_time()}] Retrieved audio for {job_id} from MinIO as {object_name}"
            )
            return result
        except Exception as e:
            print(f"[{self.get_time()}] Failed to get audio from MinIO: {e}")
            return None


def test_storage_manager():
    """Run tests for StorageManager functionality.
    
    Tests include:
    1. Initialization of StorageManager
    2. Storing audio file
    3. Retrieving stored audio file
    4. Handling non-existent file retrieval
    5. Cleanup of test data
    """
    print("\n=== Starting Storage Manager Tests ===")

    # Initialize test data
    test_job_id = f"test_{int(time.time())}"
    test_audio_content = b"fake audio content for testing"
    test_filename = f"{test_job_id}.mp3"
    test_transcription_params = TranscriptionParams(
        name="Test Podcast",
        duration=5,
        speaker_1_name="John",
        speaker_2_name="Jane",
        model="test-model",
        voice_mapping={"speaker-1": "voice1", "speaker-2": "voice2"},
    )

    # Test 1: Initialize StorageManager
    print("\nTest 1: Initializing StorageManager")
    try:
        storage_manager = StorageManager()
        print("✓ StorageManager initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize StorageManager: {e}")
        return

    # Test 2: Store audio file
    print("\nTest 2: Storing audio file")
    store_success = storage_manager.store_audio(
        test_job_id, test_audio_content, test_filename, test_transcription_params
    )
    if store_success:
        print("✓ Audio stored successfully")
    else:
        print("✗ Failed to store audio")
        return

    # Test 3: Retrieve audio file
    print("\nTest 3: Retrieving audio file")
    retrieved_content = storage_manager.get_audio(test_job_id, test_filename)
    if retrieved_content == test_audio_content:
        print("✓ Audio retrieved successfully and content matches")
    else:
        print("✗ Retrieved audio content doesn't match or retrieval failed")

    # Test 4: Try to retrieve non-existent file
    print("\nTest 4: Attempting to retrieve non-existent file")
    non_existent = storage_manager.get_audio("non_existent_job", "non_existent.mp3")
    if non_existent is None:
        print("✓ Properly handled non-existent file")
    else:
        print("✗ Unexpected behavior with non-existent file")

    # Cleanup
    print("\nCleaning up test data...")
    try:
        storage_manager.client.remove_object(
            storage_manager.bucket_name, f"{test_job_id}/{test_filename}"
        )
        print("✓ Test data cleaned up successfully")
    except Exception as e:
        print(f"✗ Failed to clean up test data: {e}")

    print("\n=== Storage Manager Tests Completed ===")


def test_get_audio_closes_response():
    """Unit test verifying get_audio closes the MinIO response object.

    MinIO get_object returns an HTTPResponse that must be closed to release
    the underlying connection. This test ensures the response is closed after
    reading to prevent connection leaks under load.
    """
    from unittest.mock import MagicMock, patch

    mock_minio_instance = MagicMock()
    mock_minio_instance.bucket_exists.return_value = True

    with patch("tests.test_db.Minio", return_value=mock_minio_instance):
        storage_manager = StorageManager()

    mock_response = MagicMock()
    mock_response.read.return_value = b"retrieved audio bytes"
    mock_minio_instance.get_object.return_value = mock_response

    result = storage_manager.get_audio("job-123", "audio.mp3")

    assert result == b"retrieved audio bytes"
    mock_minio_instance.get_object.assert_called_once_with(
        storage_manager.bucket_name, "job-123/audio.mp3"
    )
    mock_response.read.assert_called_once()
    mock_response.close.assert_called_once()


if __name__ == "__main__":
    test_storage_manager()
