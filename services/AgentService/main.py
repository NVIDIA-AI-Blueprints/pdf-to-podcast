"""
Main FastAPI application for the Agent Service.

This service coordinates the PDF-to-podcast conversion process by managing jobs,
orchestrating LLM calls, and handling both monologue and dialogue podcast generation.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from shared.api_types import (
    ServiceType,
    JobStatus,
)
from shared.podcast_types import Conversation, PodcastOutline
from shared.api_types import TranscriptionRequest
from podcast_flow import (
    podcast_summarize_pdfs,
    podcast_generate_raw_outline,
    podcast_generate_structured_outline,
    podcast_process_segments,
    podcast_generate_dialogue,
    podcast_combine_dialogues,
    podcast_create_final_conversation,
)
from monologue_flow import (
    monologue_summarize_pdfs,
    monologue_generate_raw_outline,
    monologue_generate_monologue,
    monologue_create_final_conversation,
)
from shared.storage import StorageManager
from shared.llmmanager import LLMManager
from shared.job import JobStatusManager
from shared.otel import OpenTelemetryInstrumentation, OpenTelemetryConfig
from opentelemetry.trace.status import StatusCode
import ujson as json
import os
import logging
from shared.prompt_tracker import PromptTracker


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(debug=True)

# Set up OpenTelemetry instrumentation
telemetry = OpenTelemetryInstrumentation()
config = OpenTelemetryConfig(
    service_name="agent-service",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317"),
    enable_redis=True,
    enable_requests=True,
)
telemetry.initialize(config, app)

# Initialize managers
job_manager = JobStatusManager(ServiceType.AGENT, telemetry=telemetry)
storage_manager = StorageManager(telemetry=telemetry)


async def process_transcription(job_id: str, request: TranscriptionRequest):
    """
    Main processing function for transcription requests.
    
    Handles both monologue and dialogue podcast generation workflows by coordinating
    multiple steps including PDF summarization, outline generation, and conversation creation.

    Args:
        job_id (str): Unique identifier for the transcription job
        request (TranscriptionRequest): Contains all parameters for the transcription including:
            - PDF metadata
            - Voice mapping
            - Speaker names
            - Duration target
            - Processing preferences

    Raises:
        Exception: If any step in the process fails, with error details in job status
    """
    with telemetry.tracer.start_as_current_span("agent.process_transcription") as span:
        try:
            # Initialize LLM manager and prompt tracker
            llm_manager = LLMManager(
                api_key=os.getenv("NVIDIA_API_KEY"),
                telemetry=telemetry,
                config_path=os.getenv("MODEL_CONFIG_PATH"),
            )
            span.set_attribute("model_config_path", os.getenv("MODEL_CONFIG_PATH"))
            prompt_tracker = PromptTracker(job_id, request.userId, storage_manager)

            # Initialize processing
            job_manager.update_status(
                job_id, JobStatus.PROCESSING, "Inicializando procesamiento"
            )

            if request.monologue:
                # Summarize PDFs
                summarized_pdfs = await monologue_summarize_pdfs(
                    request.pdf_metadata,
                    job_id,
                    llm_manager,
                    prompt_tracker,
                    job_manager,
                    logger,
                )

                # Generate raw outline
                raw_outline = await monologue_generate_raw_outline(
                    summarized_pdfs,
                    request,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                )

                # Generate monologue
                monologue = await monologue_generate_monologue(
                    raw_outline,
                    request,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                )

                # Create final conversation
                final_conversation = await monologue_create_final_conversation(
                    monologue, request, llm_manager, prompt_tracker, job_id, job_manager
                )

                # Store result
                job_manager.set_result_with_expiration(
                    job_id, final_conversation.model_dump_json().encode(), ex=120
                )
                job_manager.update_status(
                    job_id, JobStatus.COMPLETED, "Transcripción completada exitosamente"
                )

            else:
                # Summarize PDFs
                summarized_pdfs = await podcast_summarize_pdfs(
                    request.pdf_metadata,
                    job_id,
                    llm_manager,
                    prompt_tracker,
                    job_manager,
                    logger,
                )

                # Generate initial outline
                raw_outline = await podcast_generate_raw_outline(
                    summarized_pdfs,
                    request,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                    logger,
                )

                # Convert outline to structured format
                outline: PodcastOutline = await podcast_generate_structured_outline(
                    raw_outline,
                    request,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                    logger,
                )

                # Process segments in parallel
                segments = await podcast_process_segments(
                    outline,
                    request,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                    logger,
                )

                # Generate dialogues from segments in parallel
                segment_dialogues = await podcast_generate_dialogue(
                    segments,
                    outline,
                    request,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                    logger,
                )

                # Combine transcripts iteratively
                combined_dialogues = await podcast_combine_dialogues(
                    segment_dialogues,
                    outline,
                    llm_manager,
                    prompt_tracker,
                    job_id,
                    job_manager,
                    logger,
                )

                # Create final conversation by formatting as JSON
                final_conversation: Conversation = (
                    await podcast_create_final_conversation(
                        combined_dialogues,
                        request,
                        llm_manager,
                        prompt_tracker,
                        job_id,
                        job_manager,
                        logger,
                    )
                )
                # Store result
                job_manager.set_result_with_expiration(
                    job_id, final_conversation.model_dump_json().encode(), ex=120
                )
                job_manager.update_status(
                    job_id, JobStatus.COMPLETED, "Transcripción completada exitosamente"
                )

        except Exception as e:
            span.set_status(StatusCode.ERROR, "transcription failed")
            span.record_exception(e)
            logger.error(f"Error processing job {job_id}: {str(e)}")
            job_manager.update_status(job_id, JobStatus.FAILED, str(e))
            raise


# API Endpoints
@app.post("/transcribe", status_code=202)
def transcribe(request: TranscriptionRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to start a new transcription job.
    
    Accepts a transcription request and starts an asynchronous job to process it.
    The job runs in the background and its status can be checked using the /status endpoint.

    Args:
        request (TranscriptionRequest): Contains job parameters and PDF metadata
        background_tasks (BackgroundTasks): FastAPI background tasks handler

    Returns:
        dict: Contains the job_id for tracking the request
    """
    with telemetry.tracer.start_as_current_span("agent.transcribe") as span:
        span.set_attribute("request", request.model_dump(exclude={"markdown"}))
        job_manager.create_job(request.job_id)
        background_tasks.add_task(process_transcription, request.job_id, request)
        return {"job_id": request.job_id}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """
    Get the current status of a transcription job.

    Args:
        job_id (str): ID of the job to check

    Returns:
        dict: Current job status and details containing:
            - status: Current job status (PENDING, PROCESSING, COMPLETED, FAILED)
            - message: Status message or error details
            - progress: Optional progress information
            
    Raises:
        HTTPException: If job is not found
    """
    with telemetry.tracer.start_as_current_span("agent.get_status") as span:
        span.set_attribute("job_id", job_id)
        status = job_manager.get_status(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Job not found")
        span.set_attribute("status", status.get("status"))
        return status


@app.get("/output/{job_id}")
def get_output(job_id: str):
    """
    Get the final output of a completed transcription job.

    Args:
        job_id (str): ID of the completed job

    Returns:
        dict: The generated podcast conversation

    Raises:
        HTTPException: If result is not found
    """
    with telemetry.tracer.start_as_current_span("agent.get_output") as span:
        span.set_attribute("job_id", job_id)
        result = job_manager.get_result(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return json.loads(result.decode())


@app.get("/health")
def health():
    """
    Simple health check endpoint.

    Returns:
        dict: Service health status
    """
    return {
        "status": "healthy",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8964)
