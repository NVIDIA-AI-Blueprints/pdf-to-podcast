"""
Podcast flow module for converting PDFs to podcast conversations.

This module handles the workflow for generating multi-speaker podcast content from PDF documents.
It includes functionality for summarizing PDFs, generating outlines, and creating dialogue segments.
"""

from shared.pdf_types import PDFMetadata
from shared.podcast_types import Conversation, PodcastOutline
from shared.api_types import JobStatus, TranscriptionRequest
from shared.llmmanager import LLMManager
from shared.job import JobStatusManager
from typing import List, Dict, Any, Coroutine
import ujson as json
import logging
from shared.prompt_tracker import PromptTracker
from podcast_prompts import PodcastPrompts
from langchain_core.messages import AIMessage
import asyncio


async def podcast_summarize_pdf(
    pdf_metadata: PDFMetadata, llm_manager: LLMManager, prompt_tracker: PromptTracker
) -> AIMessage:
    """
    Summarize a single PDF document using the LLM.

    Args:
        pdf_metadata (PDFMetadata): The PDF document metadata and content to summarize
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses

    Returns:
        AIMessage: The LLM's summary response

    The function uses a template to generate a summary prompt and tracks both the
    prompt and response for monitoring purposes.
    """
    template = PodcastPrompts.get_template("podcast_summary_prompt")
    prompt = template.render(text=pdf_metadata.markdown)

    summary_response: AIMessage = await llm_manager.query_async(
        "reasoning",
        [{"role": "user", "content": prompt}],
        f"summarize_{pdf_metadata.filename}",
    )
    prompt_tracker.track(
        f"summarize_{pdf_metadata.filename}",
        prompt,
        llm_manager.model_configs["reasoning"].name,
    )
    return summary_response


async def podcast_summarize_pdfs(
    pdfs: List[PDFMetadata],
    job_id: str,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> List[PDFMetadata]:
    """
    Summarize all PDFs in parallel and update their metadata with summaries.

    Args:
        pdfs (List[PDFMetadata]): List of PDFs to summarize
        job_id (str): ID for tracking job progress
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        List[PDFMetadata]: The input PDFs with summaries added

    Uses asyncio.gather to process multiple PDFs concurrently and updates
    job status throughout the process.
    """
    job_manager.update_status(
        job_id, JobStatus.PROCESSING, f"Resumiendo {len(pdfs)} PDFs"
    )

    summaries: List[AIMessage] = await asyncio.gather(
        *[podcast_summarize_pdf(pdf, llm_manager, prompt_tracker) for pdf in pdfs]
    )

    for pdf, summary in zip(pdfs, summaries):
        pdf.summary = summary.content
        prompt_tracker.update_result(f"summarize_{pdf.filename}", pdf.summary)
        logger.info(f"Successfully summarized {pdf.filename}")

    return pdfs


async def podcast_generate_raw_outline(
    summarized_pdfs: List[PDFMetadata],
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_id: str,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> str:
    """
    Generate initial raw outline from summarized PDFs.

    Args:
        summarized_pdfs (List[PDFMetadata]): PDFs with their summaries
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_id (str): ID for tracking job progress
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        str: Raw outline text generated from the summaries

    Formats document summaries in XML and uses a template to generate
    an initial podcast outline structure.
    """
    # Prepare document summaries in XML format
    job_manager.update_status(
        job_id, JobStatus.PROCESSING, "Generando esquema inicial"
    )
    documents = []
    for pdf in summarized_pdfs:
        doc_str = f"""
        <document>
        <type>{"Target Document" if pdf.type == "target" else "Context Document"}</type>
        <path>{pdf.filename}</path>
        <summary>
        {pdf.summary}
        </summary>
        </document>"""
        documents.append(doc_str)

    template = PodcastPrompts.get_template("podcast_multi_pdf_outline_prompt")
    prompt = template.render(
        total_duration=request.duration,
        focus_instructions=request.guide if request.guide else None,
        documents="\n\n".join(documents),
    )
    raw_outline: AIMessage = await llm_manager.query_async(
        "reasoning",
        [{"role": "user", "content": prompt}],
        "raw_outline",
    )

    prompt_tracker.track(
        "raw_outline",
        prompt,
        llm_manager.model_configs["reasoning"].name,
        raw_outline.content,
    )

    return raw_outline.content


async def podcast_generate_structured_outline(
    raw_outline: str,
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_id: str,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> PodcastOutline:
    """
    Convert raw outline text to structured PodcastOutline format.

    Args:
        raw_outline (str): Raw outline text to structure
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_id (str): ID for tracking job progress
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        PodcastOutline: Structured outline following the PodcastOutline schema

    Uses JSON schema validation to ensure the outline follows the required structure
    and only references valid PDF filenames.
    """
    job_manager.update_status(
        job_id,
        JobStatus.PROCESSING,
        "Converting raw outline to structured format",
    )

    # Force the model to only reference valid filenames
    valid_filenames = [pdf.filename for pdf in request.pdf_metadata]
    schema = PodcastOutline.model_json_schema()
    schema["$defs"]["PodcastSegment"]["properties"]["references"]["items"] = {
        "type": "string",
        "enum": valid_filenames,
    }

    schema = PodcastOutline.model_json_schema()
    template = PodcastPrompts.get_template(
        "podcast_multi_pdf_structured_outline_prompt"
    )
    prompt = template.render(
        outline=raw_outline,
        schema=json.dumps(schema, indent=2),
        valid_filenames=[pdf.filename for pdf in request.pdf_metadata],
    )
    outline: Dict = await llm_manager.query_async(
        "json",
        [{"role": "user", "content": prompt}],
        "outline",
        json_schema=schema,
    )
    prompt_tracker.track(
        "outline", prompt, llm_manager.model_configs["json"].name, json.dumps(outline)
    )
    return PodcastOutline.model_validate(outline)


async def podcast_process_segment(
    segment: Any,
    idx: int,
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
) -> tuple[str, str]:
    """
    Process a single outline segment to generate initial content.

    Args:
        segment (Any): Segment from the outline to process
        idx (int): Index of the segment
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses

    Returns:
        tuple[str, str]: Tuple of (segment_id, generated_content)

    Generates initial content for a segment, incorporating referenced PDF content
    if available. Uses different templates based on whether references exist.
    """
    # Get reference content if it exists
    text_content = []
    if segment.references:
        for ref in segment.references:
            # Find matching PDF metadata by filename
            pdf = next(
                (pdf for pdf in request.pdf_metadata if pdf.filename == ref), None
            )
            if pdf:
                text_content.append(pdf.markdown)

    # Choose template based on whether we have references
    template_name = (
        "podcast_prompt_with_references"
        if text_content
        else "podcast_prompt_no_references"
    )
    template = PodcastPrompts.get_template(template_name)

    # Prepare prompt parameters
    prompt_params = {
        "duration": segment.duration,
        "topic": segment.section,
        "angles": "\n".join([topic.title for topic in segment.topics]),
    }

    # Add text content if we have references
    if text_content:
        prompt_params["text"] = "\n\n".join(text_content)

    prompt = template.render(**prompt_params)

    response: AIMessage = await llm_manager.query_async(
        "iteration",
        [{"role": "user", "content": prompt}],
        f"segment_{idx}",
    )

    prompt_tracker.track(
        f"segment_transcript_{idx}",
        prompt,
        llm_manager.model_configs["iteration"].name,
        response.content,
    )

    return f"segment_transcript_{idx}", response.content


async def podcast_process_segments(
    outline: PodcastOutline,
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_id: str,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> Dict[str, str]:
    """
    Process all outline segments in parallel to generate initial content.

    Args:
        outline (PodcastOutline): Structured outline to process
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_id (str): ID for tracking job progress
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        Dict[str, str]: Dictionary mapping segment IDs to their generated content

    Creates tasks for processing each segment and executes them in parallel using
    asyncio.gather.
    """
    # Create tasks for processing each segment
    segment_tasks: List[Coroutine] = []
    for idx, segment in enumerate(outline.segments):
        job_manager.update_status(
            job_id,
            JobStatus.PROCESSING,
            f"Procesando segmento {idx + 1}/{len(outline.segments)}: {segment.section}",
        )

        task = podcast_process_segment(
            segment,
            idx,
            request,
            llm_manager,
            prompt_tracker,
        )
        segment_tasks.append(task)

    # Process all segments in parallel
    results = await asyncio.gather(*segment_tasks)

    # Convert results to dictionary
    return dict(results)


async def podcast_generate_dialogue_segment(
    segment: Any,
    idx: int,
    segment_text: str,
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
) -> Dict[str, str]:
    """
    Generate dialogue for a single segment.

    Args:
        segment (Any): Segment from the outline
        idx (int): Index of the segment
        segment_text (str): Generated content for the segment
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses

    Returns:
        Dict[str, str]: Dictionary containing section name and generated dialogue

    Formats segment topics and uses a template to convert content into a dialogue
    format between two speakers.
    """
    # Format topics for prompt
    topics_text = "\n".join(
        [
            f"- {topic.title}\n"
            + "\n".join([f"  * {point.description}" for point in topic.points])
            for topic in segment.topics
        ]
    )

    # Generate dialogue using template
    template = PodcastPrompts.get_template("podcast_transcript_to_dialogue_prompt")
    prompt = template.render(
        text=segment_text,
        duration=segment.duration,
        descriptions=topics_text,
        speaker_1_name=request.speaker_1_name,
        speaker_2_name=request.speaker_2_name,
    )

    # Query LLM for dialogue
    dialogue_response = await llm_manager.query_async(
        "reasoning",
        [{"role": "user", "content": prompt}],
        f"segment_dialogue_{idx}",
    )

    # Track prompt and response
    prompt_tracker.track(
        f"segment_dialogue_{idx}",
        prompt,
        llm_manager.model_configs["reasoning"].name,
        dialogue_response.content,
    )

    return {"section": segment.section, "dialogue": dialogue_response.content}


async def podcast_generate_dialogue(
    segments: Dict[str, str],
    outline: PodcastOutline,
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_id: str,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> List[Dict[str, str]]:
    """
    Generate dialogue for all segments in parallel.

    Args:
        segments (Dict[str, str]): Dictionary of segment IDs and their content
        outline (PodcastOutline): Structured outline
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_id (str): ID for tracking job progress
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        List[Dict[str, str]]: List of dictionaries containing section names and dialogues

    Creates tasks for generating dialogue for each segment and executes them in parallel.
    """
    job_manager.update_status(job_id, JobStatus.PROCESSING, "Generando diálogo")

    # Create tasks for generating dialogue for each segment
    dialogue_tasks = []
    for idx, segment in enumerate(outline.segments):
        segment_name = f"segment_transcript_{idx}"
        seg_response = segments.get(segment_name)

        if not seg_response:
            logger.warning(f"Segment {segment_name} not found in segment transcripts")
            continue

        # Update prompt tracker with segment response
        segment_text = seg_response
        prompt_tracker.update_result(segment_name, segment_text)

        # Update status
        job_manager.update_status(
            job_id,
            JobStatus.PROCESSING,
            f"Convirtiendo segmento {idx + 1}/{len(outline.segments)} a diálogo",
        )

        task = podcast_generate_dialogue_segment(
            segment,
            idx,
            segment_text,
            request,
            llm_manager,
            prompt_tracker,
        )
        dialogue_tasks.append(task)

    # Process all dialogues in parallel
    dialogues = await asyncio.gather(*dialogue_tasks)

    return list(dialogues)


async def podcast_combine_dialogues(
    segment_dialogues: List[Dict[str, str]],
    outline: PodcastOutline,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_id: str,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> str:
    """
    Iteratively combine dialogue segments into a cohesive conversation.

    Args:
        segment_dialogues (List[Dict[str, str]]): List of segment dialogues
        outline (PodcastOutline): Structured outline
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_id (str): ID for tracking job progress
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        str: Combined dialogue text

    Iteratively combines dialogue segments, ensuring smooth transitions between sections.
    """
    job_manager.update_status(
        job_id, JobStatus.PROCESSING, "Combinando segmentos de diálogo"
    )

    # Start with the first segment's dialogue
    current_dialogue = segment_dialogues[0]["dialogue"]
    prompt_tracker.update_result(
        "segment_dialogue_0",
        current_dialogue,
    )

    # Iteratively combine with subsequent segments
    for idx in range(1, len(segment_dialogues)):
        job_manager.update_status(
            job_id,
            JobStatus.PROCESSING,
            f"Combinando segmento {idx + 1}/{len(segment_dialogues)} con diálogo existente",
        )

        next_section = segment_dialogues[idx]["dialogue"]
        prompt_tracker.update_result(f"segment_dialogue_{idx}", next_section)
        current_section = segment_dialogues[idx]["section"]

        template = PodcastPrompts.get_template("podcast_combine_dialogues_prompt")
        prompt = template.render(
            outline=outline.model_dump_json(),
            dialogue_transcript=current_dialogue,
            next_section=next_section,
            current_section=current_section,
        )

        combined: AIMessage = await llm_manager.query_async(
            "iteration",
            [{"role": "user", "content": prompt}],
            f"combine_dialogues_{idx}",
        )

        prompt_tracker.track(
            f"combine_dialogues_{idx}",
            prompt,
            llm_manager.model_configs["iteration"].name,
            combined.content,
        )

        current_dialogue = combined.content

    return current_dialogue


async def podcast_create_final_conversation(
    dialogue: str,
    request: TranscriptionRequest,
    llm_manager: LLMManager,
    prompt_tracker: PromptTracker,
    job_id: str,
    job_manager: JobStatusManager,
    logger: logging.Logger,
) -> Conversation:
    """
    Convert the dialogue into structured Conversation format.

    Args:
        dialogue (str): Combined dialogue text
        request (TranscriptionRequest): Original transcription request
        llm_manager (LLMManager): Manager for LLM interactions
        prompt_tracker (PromptTracker): Tracks prompts and responses
        job_id (str): ID for tracking job progress
        job_manager (JobStatusManager): Manages job status updates
        logger (logging.Logger): Logger for tracking progress

    Returns:
        Conversation: Structured conversation following the Conversation schema

    Formats the dialogue into a structured conversation format with proper speaker
    attribution and timing information.
    """
    job_manager.update_status(
        job_id, JobStatus.PROCESSING, "Formateando conversación final"
    )

    schema = Conversation.model_json_schema()
    template = PodcastPrompts.get_template("podcast_dialogue_prompt")
    prompt = template.render(
        speaker_1_name=request.speaker_1_name,
        speaker_2_name=request.speaker_2_name,
        text=dialogue,
        schema=json.dumps(schema, indent=2),
    )

    # We accumulate response as it comes in then cast
    conversation_json: Dict = await llm_manager.stream_async(
        "json",
        [{"role": "user", "content": prompt}],
        "create_final_conversation",
        json_schema=schema,
    )

    # Ensure all strings are unescaped
    if "dialogues" in conversation_json:
        for entry in conversation_json["dialogues"]:
            if "text" in entry:
                entry["text"] = unescape_unicode_string(entry["text"])

    prompt_tracker.track(
        "create_final_conversation",
        prompt,
        llm_manager.model_configs["json"].name,
        json.dumps(conversation_json),
    )

    return Conversation.model_validate(conversation_json)


def unescape_unicode_string(s: str) -> str:
    """
    Convert escaped Unicode sequences to actual Unicode characters.

    Args:
        s (str): String potentially containing escaped Unicode sequences

    Returns:
        str: String with Unicode sequences converted to actual characters

    Example:
        >>> unescape_unicode_string("Hello\\u2019s World")
        "Hello's World"
    """
    # This handles both raw strings (with extra backslashes) and regular strings
    return s.encode("utf-8").decode("unicode-escape")
