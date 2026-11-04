from typing import Dict
import time
import logging
from .storage import StorageManager
from .prompt_types import ProcessingStep, PromptTracker as PromptTrackerModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PromptTracker:
    """Track prompts and responses and save them to storage.

    This class provides functionality to track and store prompts, responses and processing
    steps for a given job. It maintains a history of interactions that can be persisted
    to storage.

    Attributes:
        job_id (str): Unique identifier for the job being tracked
        user_id (str): Identifier for the user who owns this job
        steps (Dict[str, ProcessingStep]): Dictionary mapping step names to processing steps
        storage_manager (StorageManager): Manager for persisting data to storage
    """

    def __init__(self, job_id: str, user_id: str, storage_manager: StorageManager):
        """Initialize a new PromptTracker instance.

        Args:
            job_id (str): Unique identifier for the job
            user_id (str): Identifier for the user
            storage_manager (StorageManager): Storage manager instance for persistence
        """
        self.job_id = job_id
        self.user_id = user_id
        self.steps: Dict[str, ProcessingStep] = {}
        self.storage_manager = storage_manager

    def track(self, step_name: str, prompt: str, model: str, response: str = None):
        """Track a processing step

        Creates a new ProcessingStep entry and optionally saves it if a response is provided.

        Args:
            step_name (str): Name identifying this processing step
            prompt (str): The prompt text used
            model (str): Name/identifier of the model used
            response (str, optional): Response received from the model. Defaults to None.
        """
        self.steps[step_name] = ProcessingStep(
            step_name=step_name,
            prompt=prompt,
            response=response if response else "",
            model=model,
            timestamp=time.time(),
        )
        if response:
            self._save()
        logger.info(f"Tracked step {step_name} for {self.job_id}")

    def update_result(self, step_name: str, response: str):
        """Save the current state to storage

        Args:
            step_name (str): Name of the step to update
            response (str): New response text to store

        Note:
            If the step_name doesn't exist, a warning will be logged and no update occurs.
        """
        if step_name in self.steps:
            self.steps[step_name].response = response
            self._save()
            logger.info(f"Updated response for step {step_name}")
        else:
            logger.warning(f"Step {step_name} not found in prompt tracker")

    def _save(self):
        """Save the current state to storage

        Converts the tracked steps to JSON format and stores them using the storage manager.
        The file is saved with a name based on the job_id.
        """
        tracker = PromptTrackerModel(steps=list(self.steps.values()))
        self.storage_manager.store_file(
            self.user_id,
            self.job_id,
            tracker.model_dump_json().encode(),
            f"{self.job_id}_prompt_tracker.json",
            "application/json",
        )
        logger.info(
            f"Stored prompt tracker for {self.job_id} in minio. Length: {len(self.steps)}"
        )
