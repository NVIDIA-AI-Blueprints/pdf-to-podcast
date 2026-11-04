from pydantic import BaseModel, Field
from typing import Optional, Union, Literal
from datetime import datetime
from enum import Enum


class ConversionStatus(str, Enum):
    """Enum representing the status of a PDF conversion.

    This enum is used to track the success or failure state of PDF conversion operations.

    Attributes:
        SUCCESS: Indicates successful conversion
        FAILED: Indicates failed conversion
    """

    SUCCESS = "success"
    FAILED = "failed"


class PDFConversionResult(BaseModel):
    """Model representing the result of a PDF conversion operation.

    This model captures the output and status of converting a PDF file to text.
    It includes both successful conversions with extracted content and failed
    conversions with error details.

    Attributes:
        filename (str): Name of the PDF file
        content (str): Extracted text content from the PDF
        status (ConversionStatus): Status of the conversion operation
        error (Optional[str]): Error message if conversion failed
    """

    filename: str
    content: str = ""
    status: ConversionStatus
    error: Optional[str] = None


class PDFMetadata(BaseModel):
    """Model representing metadata about a processed PDF document.

    This model stores metadata and processing results for a PDF document, including
    both the converted content in markdown format and a generated summary. It tracks
    whether the document is a primary target or supplementary context document.

    Attributes:
        filename (str): Name of the PDF file
        markdown (str): Markdown representation of the PDF content
        summary (str): Generated summary of the PDF content
        status (ConversionStatus): Status of the PDF processing
        type (Union[Literal["target"], Literal["context"]]): Whether this is a target or context document
        error (Optional[str]): Error message if processing failed
        created_at (datetime): Timestamp when this metadata was created
    """

    filename: str
    markdown: str = ""
    summary: str = ""
    status: ConversionStatus
    type: Union[Literal["target"], Literal["context"]]
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
