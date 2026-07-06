from celery import Celery
import os
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

celery_app = Celery(
    "pdf_converter",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max runtime
    task_soft_time_limit=3300,  # 55 minutes soft limit
)


@celery_app.task(bind=True, max_retries=3)
def convert_pdf_task(self, file_paths: List[str]) -> List[Dict[str, str]]:
    try:
        # XPU: OCR disabled. docling >= 2.5 otherwise downloads a RapidOCR
        # model at runtime, which fails in an offline / proxied container.
        # Text-native (typeset) PDFs do not need OCR. Set
        # do_ocr = True only if scanned PDFs must be supported and the OCR
        # model is reachable. See XPU_MIGRATION.md.
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True
        converter = DocumentConverter(
            format_options={
                "pdf": PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        results = []
        conversion_results = converter.convert_all(
            file_paths,
            raises_on_error=True,
        )

        for result in conversion_results:
            file_path = str(result.input.file)
            try:
                if result.status in {
                    ConversionStatus.SUCCESS,
                    ConversionStatus.PARTIAL_SUCCESS,
                }:
                    markdown = result.document.export_to_markdown()
                    results.append(
                        {
                            "filename": os.path.basename(file_path),
                            "status": "success",
                            "content": markdown,
                        }
                    )
                else:
                    error_msg = (
                        "; ".join(str(error) for error in result.errors)
                        if result.errors
                        else f"Conversion failed with status: {result.status}"
                    )
                    logger.error(f"Failed to convert {file_path}: {error_msg}")
                    results.append(
                        {
                            "filename": os.path.basename(file_path),
                            "status": "failed",
                            "error": error_msg,
                        }
                    )
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
                except Exception as e:
                    logger.error(f"Error cleaning up file: {e}")

        return results

    except Exception as exc:
        logger.error(f"Error in batch conversion: {exc}")
        retry_in = 5 * (2**self.request.retries)
        raise self.retry(exc=exc, countdown=retry_in)
