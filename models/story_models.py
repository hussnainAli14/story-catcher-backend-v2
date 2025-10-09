from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
import uuid

@dataclass
class Question:
    """Represents a story question"""
    id: int
    text: str
    category: str
    order: int

@dataclass
class Answer:
    """Represents a user's answer to a question"""
    question_id: int
    answer_text: str
    timestamp: datetime

@dataclass
class StorySession:
    """Represents a complete story session"""
    session_id: str
    created_at: datetime
    answers: List[Answer]
    current_question: int
    is_complete: bool
    generated_story: Optional[str] = None
    user_email: Optional[str] = None
    
    def to_dict(self):
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'answers': [asdict(answer) for answer in self.answers],
            'current_question': self.current_question,
            'is_complete': self.is_complete,
            'generated_story': self.generated_story,
            'user_email': self.user_email
        }

@dataclass
class StoryResponse:
    """Response model for API endpoints"""
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None
