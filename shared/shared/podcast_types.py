from pydantic import BaseModel
from typing import Optional, Dict, Literal, List


class SavedPodcast(BaseModel):
    """Model representing a saved podcast file.
    
    Attributes:
        job_id (str): Unique identifier for the podcast generation job
        filename (str): Name of the saved podcast file
        created_at (str): Timestamp when podcast was created
        size (int): Size of the podcast file in bytes
        transcription_params (Optional[Dict]): Optional parameters used for transcription
    """
    job_id: str
    filename: str
    created_at: str
    size: int
    transcription_params: Optional[Dict] = {}


class SavedPodcastWithAudio(SavedPodcast):
    """Model extending SavedPodcast to include audio data.
    
    Attributes:
        audio_data (str): Base64 encoded audio data of the podcast
    """
    audio_data: str


class DialogueEntry(BaseModel):
    """Model representing a single dialogue entry in a conversation.
    
    Attributes:
        text (str): The spoken text content
        speaker (Literal["speaker-1", "speaker-2"]): Identifier for which speaker is talking
    """
    text: str
    speaker: Literal["speaker-1", "speaker-2"]


class Conversation(BaseModel):
    """Model representing a conversation between two speakers.
    
    Attributes:
        scratchpad (str): Working notes or context for the conversation
        dialogue (List[DialogueEntry]): List of dialogue entries making up the conversation
    """
    scratchpad: str = ""
    dialogue: List[DialogueEntry]


class SegmentPoint(BaseModel):
    """Model representing a key point within a podcast segment topic.
    
    Attributes:
        description (str): Description of the point to be covered
    """
    description: str


class SegmentTopic(BaseModel):
    """Model representing a topic within a podcast segment.
    
    Attributes:
        title (str): Title of the topic
        points (List[SegmentPoint]): List of key points to cover in the topic
    """
    title: str
    points: List[SegmentPoint]


class PodcastSegment(BaseModel):
    """Model representing a segment of a podcast.
    
    Attributes:
        section (str): Name or title of the segment
        topics (List[SegmentTopic]): List of topics to cover in the segment
        duration (int): Duration of the segment in seconds
        references (List[str]): List of reference sources for the segment content
    """
    section: str
    topics: List[SegmentTopic]
    duration: int
    references: List[str]


class PodcastOutline(BaseModel):
    """Model representing the complete outline of a podcast.
    
    Attributes:
        title (str): Title of the podcast
        segments (List[PodcastSegment]): List of segments making up the podcast
    """
    title: str
    segments: List[PodcastSegment]
