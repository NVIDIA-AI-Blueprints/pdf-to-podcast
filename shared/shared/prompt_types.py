from pydantic import BaseModel
from typing import List


class ProcessingStep(BaseModel):
    """Model representing a single processing step in an AI interaction.

    This model captures details about a specific interaction with an AI model,
    including the prompt used, response received, and timing information.

    Attributes:
        step_name (str): Name identifying this processing step
        prompt (str): The prompt text sent to the model
        response (str): The response received from the model
        model (str): Name/identifier of the AI model used
        timestamp (float): Unix timestamp when this step occurred
    """

    step_name: str
    prompt: str
    response: str
    model: str
    timestamp: float


class PromptTracker(BaseModel):
    """Model for tracking a sequence of AI processing steps.

    This model maintains an ordered list of processing steps that occurred
    during a job, providing a complete history of AI interactions.

    Attributes:
        steps (List[ProcessingStep]): Ordered list of processing steps that occurred
    """

    steps: List[ProcessingStep]
