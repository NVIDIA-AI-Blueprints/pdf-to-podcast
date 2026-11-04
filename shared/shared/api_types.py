from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, List
from .pdf_types import PDFMetadata
from enum import Enum


class JobStatus(str, Enum):
    """Enum representing the possible states of a job."""

    PENDING = "pending"  # Job has been created but not started
    PROCESSING = "processing"  # Job is currently being processed
    COMPLETED = "completed"  # Job has finished successfully
    FAILED = "failed"  # Job encountered an error and failed


class ServiceType(str, Enum):
    """Enum representing the different service types in the system."""

    PDF = "pdf"  # PDF processing service
    AGENT = "agent"  # Agent/LLM service
    TTS = "tts"  # Text-to-speech service


class StatusUpdate(BaseModel):
    """Model for job status updates sent between services."""

    job_id: str
    status: JobStatus
    message: Optional[str] = None  # Optional status message
    service: Optional[ServiceType] = None  # Service sending the update
    timestamp: Optional[float] = None  # Unix timestamp of update
    data: Optional[dict] = None  # Additional status data


class StatusResponse(BaseModel):
    """Model for API status responses."""

    status: str  # Overall status of the operation
    result: Optional[str] = None  # Optional success result
    error: Optional[str] = None  # Optional error message
    message: Optional[str] = None  # Optional status message


class TranscriptionParams(BaseModel):
    """Base parameters for podcast transcription requests."""

    userId: str = Field(..., description="KAS User ID")
    name: str = Field(..., description="Name of the podcast")
    duration: int = Field(..., description="Duration in minutes")
    monologue: bool = Field(
        False, description="If True, creates a single-speaker podcast"
    )
    speaker_1_name: str = Field(
        ..., description="Name of the speaker (or first speaker if not monologue)"
    )
    speaker_2_name: Optional[str] = Field(
        None, description="Name of the second speaker (not required for monologue)"
    )
    voice_mapping: Dict[str, str] = Field(
        ...,
        description="Mapping of speaker IDs to voice IDs. For monologue, only speaker-1 is required",
        example={
            "speaker-1": "iP95p4xoKVk53GoZ742B",
            "speaker-2": "9BWtsMINqrJLrRacOk9x",
        },
    )
    guide: Optional[str] = Field(
        None, description="Optional guidance for the transcription focus and structure"
    )
    vdb_task: bool = Field(
        False,
        description="If True, creates a VDB task when running NV-Ingest allowing for retrieval abilities",
    )

    @model_validator(mode="after")
    def validate_monologue_settings(self) -> "TranscriptionParams":
        """
        Validates the configuration based on monologue/dialogue mode.

        For monologue mode:
        - No second speaker name should be provided
        - Voice mapping should only contain speaker-1

        For dialogue mode:
        - Second speaker name is required
        - Voice mapping must contain both speakers

        Returns:
            TranscriptionParams: The validated model instance

        Raises:
            ValueError: If validation fails
        """
        if self.monologue:
            # Check speaker_2_name is not provided
            if self.speaker_2_name is not None:
                raise ValueError(
                    "speaker_2_name should not be provided for monologue podcasts"
                )

            # Check voice_mapping only contains speaker-1
            if "speaker-2" in self.voice_mapping:
                raise ValueError(
                    "voice_mapping should only contain speaker-1 for monologue podcasts"
                )

            # Check that speaker-1 is present in voice_mapping
            if "speaker-1" not in self.voice_mapping:
                raise ValueError("voice_mapping must contain speaker-1")
        else:
            # For dialogues, ensure both speakers are present
            if not self.speaker_2_name:
                raise ValueError("speaker_2_name is required for dialogue podcasts")

            required_speakers = {"speaker-1", "speaker-2"}
            if not all(speaker in self.voice_mapping for speaker in required_speakers):
                raise ValueError(
                    "voice_mapping must contain both speaker-1 and speaker-2 for dialogue podcasts"
                )

        return self


class TranscriptionRequest(TranscriptionParams):
    """
    Complete transcription request model extending TranscriptionParams.
    Includes PDF metadata and job tracking information.
    """

    pdf_metadata: List[PDFMetadata]  # List of PDFs to process
    job_id: str  # Unique identifier for the transcription job


class RAGRequest(BaseModel):
    """Model for Retrieval-Augmented Generation (RAG) requests."""

    query: str = Field(..., description="The search query to process")
    k: int = Field(..., description="Number of results to retrieve", ge=1)
    job_id: str = Field(..., description="The unique job identifier")
