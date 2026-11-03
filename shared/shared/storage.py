import io
import ujson as json
import base64
from minio import Minio
from minio.error import S3Error
from shared.api_types import TranscriptionParams
from shared.otel import OpenTelemetryInstrumentation
from opentelemetry.trace.status import StatusCode
import os
import logging
import urllib3
from urllib3 import Retry
from urllib3.util import Timeout
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Minio config
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "audio-results")


# TODO: use this to wrap redis as well
# TODO: wrap errors in StorageError
# TODO: implement cleanup and delete as well
class StorageManager:
    """Manages storage operations using MinIO as the backend.

    This class provides an interface for storing and retrieving files using MinIO,
    with support for user isolation, job tracking, and metadata management.

    Attributes:
        telemetry (OpenTelemetryInstrumentation): Instance for tracing operations
        client (Minio): MinIO client instance
        bucket_name (str): Name of the MinIO bucket to use
    """

    def __init__(self, telemetry: OpenTelemetryInstrumentation):
        """Initialize MinIO client and ensure bucket exists.
        requires: OpenTelemetryInstrumentation instance for tracing since Minio
        does not have an auto otel instrumentor

        Requires:
        Args:
            telemetry (OpenTelemetryInstrumentation): Instance for tracing since MinIO
                does not have an auto OpenTelemetry instrumentor

        Raises:
            Exception: If MinIO client initialization fails
        """
        try:
            self.telemetry: OpenTelemetryInstrumentation = telemetry
            # pass in http_client for tracing
            http_client = urllib3.PoolManager(
                timeout=Timeout(connect=5, read=5),
                maxsize=10,
                retries=Retry(
                    total=5, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504]
                ),
            )
            self.client = Minio(
                os.getenv("MINIO_ENDPOINT", "minio:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
                secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
                http_client=http_client,
            )

            self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "audio-results")
            self._ensure_bucket_exists()
            logger.info("Successfully initialized MinIO storage")

        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    def _ensure_bucket_exists(self):
        """Ensure the configured bucket exists, creating it if necessary.

        Raises:
            Exception: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            raise

    def _get_object_path(self, user_id: str, job_id: str, filename: str) -> str:
        """Generate the full object path including user isolation.

        Args:
            user_id (str): ID of the user
            job_id (str): ID of the job
            filename (str): Name of the file

        Returns:
            str: Full object path in format "user_id/job_id/filename"
        """
        return f"{user_id}/{job_id}/{filename}"

    def store_file(
        self,
        user_id: str,
        job_id: str,
        content: bytes,
        filename: str,
        content_type: str,
        metadata: dict = None,
    ) -> None:
        """Store any file type in MinIO with metadata.

        Args:
            user_id (str): ID of the user
            job_id (str): ID of the job
            content (bytes): File content to store
            filename (str): Name of the file
            content_type (str): MIME type of the file
            metadata (dict, optional): Additional metadata to store. Defaults to None.

        Raises:
            Exception: If file storage fails
        """
        with self.telemetry.tracer.start_as_current_span("store_file") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("job_id", job_id)
            span.set_attribute("filename", filename)
            try:
                object_name = self._get_object_path(user_id, job_id, filename)
                self.client.put_object(
                    self.bucket_name,
                    object_name,
                    io.BytesIO(content),
                    length=len(content),
                    content_type=content_type,
                    metadata=metadata.model_dump()
                    if hasattr(metadata, "model_dump")
                    else metadata,
                )
            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(
                    f"Failed to store file {filename} for user {user_id}, job {job_id}: {str(e)}"
                )
                raise

    def store_audio(
        self,
        user_id: str,
        job_id: str,
        audio_content: bytes,
        filename: str,
        transcription_params: TranscriptionParams,
    ):
        """Store audio file with metadata in MinIO.

        Args:
            user_id (str): ID of the user
            job_id (str): ID of the job
            audio_content (bytes): Audio file content
            filename (str): Name of the audio file
            transcription_params (TranscriptionParams): Parameters used for transcription

        Raises:
            S3Error: If MinIO storage operation fails
        """
        with self.telemetry.tracer.start_as_current_span("store_audio") as span:
            span.set_attribute("job_id", job_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("filename", filename)
            try:
                object_name = self._get_object_path(user_id, job_id, filename)

                # Convert transcription params to JSON string for metadata
                params_json = json.dumps(transcription_params.model_dump())

                # Create metadata dictionary with transcription params
                metadata = {"X-Amz-Meta-Transcription-Params": params_json}

                self.client.put_object(
                    self.bucket_name,
                    object_name,
                    io.BytesIO(audio_content),
                    len(audio_content),
                    content_type="audio/mpeg",
                    metadata=metadata,
                )
                logger.info(
                    f"Stored audio for user {user_id}, job {job_id} in MinIO as {object_name} with metadata"
                )

            except S3Error as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(f"Failed to store audio in MinIO: {e}")
                raise

    def get_podcast_audio(self, user_id: str, job_id: str) -> Optional[str]:
        """Get the audio data for a specific podcast by job_id.

        Args:
            user_id (str): ID of the user
            job_id (str): ID of the job

        Returns:
            Optional[str]: Base64 encoded audio data if found, None otherwise

        Raises:
            Exception: If retrieval fails
        """
        with self.telemetry.tracer.start_as_current_span("get_podcast_audio") as span:
            span.set_attribute("job_id", job_id)
            span.set_attribute("user_id", user_id)
            try:
                # Find the file with matching user_id and job_id
                prefix = f"{user_id}/{job_id}/"
                objects = self.client.list_objects(
                    self.bucket_name, prefix=prefix, recursive=True
                )

                for obj in objects:
                    if obj.object_name.endswith(".mp3"):
                        span.set_attribute("audio_file", obj.object_name)
                        response = self.client.get_object(
                            self.bucket_name, obj.object_name
                        )
                        try:
                            audio_data = response.read()
                        finally:
                            response.close()
                            response.release_conn()
                        return base64.b64encode(audio_data).decode("utf-8")

                return None

            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(
                    f"Failed to get audio for user {user_id}, job {job_id}: {str(e)}"
                )
                raise

    def get_file(self, user_id: str, job_id: str, filename: str) -> Optional[bytes]:
        """Get any file from storage by user_id, job_id and filename.

        Args:
            user_id (str): ID of the user
            job_id (str): ID of the job
            filename (str): Name of the file to retrieve

        Returns:
            Optional[bytes]: File content if found, None if file doesn't exist

        Raises:
            Exception: If retrieval fails for reasons other than missing file
        """
        with self.telemetry.tracer.start_as_current_span("get_file") as span:
            span.set_attribute("job_id", job_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("filename", filename)
            try:
                object_name = self._get_object_path(user_id, job_id, filename)

                try:
                    response = self.client.get_object(self.bucket_name, object_name)
                    try:
                        return response.read()
                    finally:
                        response.close()
                        response.release_conn()
                except S3Error as e:
                    span.set_attribute("error", str(e))
                    if e.code == "NoSuchKey":
                        return None
                    raise

            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(
                    f"Failed to get file {filename} for user {user_id}, job {job_id}: {str(e)}"
                )
                raise

    def delete_job_files(self, user_id: str, job_id: str) -> bool:
        """Delete all files associated with a user_id and job_id.

        Args:
            user_id (str): ID of the user
            job_id (str): ID of the job

        Returns:
            bool: True if deletion successful, False otherwise
        """
        with self.telemetry.tracer.start_as_current_span("delete_job_files") as span:
            span.set_attribute("job_id", job_id)
            span.set_attribute("user_id", user_id)
            try:
                # List all objects with the user_id/job_id prefix
                prefix = f"{user_id}/{job_id}/"
                objects = self.client.list_objects(
                    self.bucket_name, prefix=prefix, recursive=True
                )

                # Delete each object
                for obj in objects:
                    self.client.remove_object(self.bucket_name, obj.object_name)
                    logger.info(f"Deleted object: {obj.object_name}")

                return True

            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(
                    f"Failed to delete files for user {user_id}, job {job_id}: {str(e)}"
                )
                return False

    def list_files_metadata(self, user_id: str = None):
        """Lists metadata filtered by user_id if provided.

        Args:
            user_id (str, optional): ID of user to filter results. Defaults to None.

        Returns:
            list: List of dictionaries containing file metadata

        Raises:
            Exception: If listing fails
        """
        with self.telemetry.tracer.start_as_current_span("list_files_metadata") as span:
            try:
                # If user_id is provided, use it as prefix to filter results
                prefix = f"{user_id}/" if user_id else ""
                span.set_attribute("user_id", user_id)
                span.set_attribute("prefix", prefix)

                objects = self.client.list_objects(
                    self.bucket_name, prefix=prefix, recursive=True
                )
                files = []

                for obj in objects:
                    logger.info(f"Object: {obj.object_name}")
                    if obj.object_name.endswith("/"):
                        continue

                    try:
                        stat = self.client.stat_object(
                            self.bucket_name, obj.object_name
                        )
                        path_parts = obj.object_name.split("/")
                        logger.info(f"Path parts: {path_parts}")

                        if not path_parts[-1].endswith(".mp3"):
                            continue

                        # Update to handle new path structure: user_id/job_id/filename
                        user_id = path_parts[0]
                        job_id = path_parts[1]

                        file_info = {
                            "user_id": user_id,
                            "job_id": job_id,
                            "filename": path_parts[-1],
                            "size": stat.size,
                            "created_at": obj.last_modified.isoformat(),
                            "path": obj.object_name,
                            "transcription_params": {},
                        }

                        if stat.metadata:
                            try:
                                params = stat.metadata.get(
                                    "X-Amz-Meta-Transcription-Params"
                                )
                                if params:
                                    file_info["transcription_params"] = json.loads(
                                        params
                                    )
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Could not parse transcription params for {obj.object_name}"
                                )

                        files.append(file_info)
                        logger.info(
                            f"Found file: {obj.object_name}, size: {stat.size} bytes"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error processing object {obj.object_name}: {str(e)}"
                        )
                        continue

                files.sort(key=lambda x: x["created_at"], reverse=True)
                logger.info(
                    f"Successfully listed {len(files)} metadata for {len(files)} files from MinIO"
                )
                return files

            except Exception as e:
                span.set_status(StatusCode.ERROR)
                span.record_exception(e)
                logger.error(f"Failed to list files from MinIO: {str(e)}")
                raise
