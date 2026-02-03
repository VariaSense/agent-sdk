"""Human feedback collection and management."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import uuid


class FeedbackType(Enum):
    """Type of human feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CORRECTIVE = "corrective"
    CLARIFICATION = "clarification"
    ANNOTATION = "annotation"


@dataclass
class HumanFeedback:
    """Human feedback on agent decision.
    
    Attributes:
        feedback_id: Unique feedback identifier
        decision_id: ID of decision being feedback on
        feedback_type: Type of feedback
        content: Feedback content/comment
        rating: Rating (1-5 scale)
        suggested_action: Suggested correction
        annotator: Who provided feedback
        created_at: Feedback timestamp
    """
    
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    feedback_type: FeedbackType = FeedbackType.POSITIVE
    content: str = ""
    rating: Optional[int] = None
    suggested_action: Optional[str] = None
    annotator: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_positive(self) -> bool:
        """Check if feedback is positive."""
        return self.feedback_type == FeedbackType.POSITIVE or (
            self.rating is not None and self.rating >= 4
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feedback_id": self.feedback_id,
            "decision_id": self.decision_id,
            "feedback_type": self.feedback_type.value,
            "content": self.content,
            "rating": self.rating,
            "suggested_action": self.suggested_action,
            "annotator": self.annotator,
            "created_at": self.created_at.isoformat(),
        }


class FeedbackCollector:
    """Collects and manages human feedback.
    
    Aggregates feedback from multiple sources and provides
    analytics on decision quality.
    """
    
    def __init__(self):
        """Initialize collector."""
        self.feedbacks: Dict[str, HumanFeedback] = {}
        self.decision_feedbacks: Dict[str, List[HumanFeedback]] = {}
    
    def submit_feedback(self, feedback: HumanFeedback) -> str:
        """Submit human feedback.
        
        Args:
            feedback: HumanFeedback instance
            
        Returns:
            Feedback ID
        """
        self.feedbacks[feedback.feedback_id] = feedback
        
        if feedback.decision_id not in self.decision_feedbacks:
            self.decision_feedbacks[feedback.decision_id] = []
        self.decision_feedbacks[feedback.decision_id].append(feedback)
        
        return feedback.feedback_id
    
    def get_feedback(self, feedback_id: str) -> Optional[HumanFeedback]:
        """Get feedback by ID."""
        return self.feedbacks.get(feedback_id)
    
    def get_decision_feedback(self, decision_id: str) -> List[HumanFeedback]:
        """Get all feedback for a decision.
        
        Args:
            decision_id: Decision identifier
            
        Returns:
            List of HumanFeedback instances
        """
        return self.decision_feedbacks.get(decision_id, [])
    
    def get_decision_quality_score(self, decision_id: str) -> float:
        """Get quality score for a decision (0.0-1.0).
        
        Combines ratings and positive feedback percentage.
        
        Args:
            decision_id: Decision identifier
            
        Returns:
            Score from 0.0 to 1.0
        """
        feedbacks = self.get_decision_feedback(decision_id)
        if not feedbacks:
            return 0.5  # Unknown
        
        # Calculate from ratings
        ratings = [f.rating for f in feedbacks if f.rating is not None]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            rating_score = avg_rating / 5.0
        else:
            rating_score = 0.0
        
        # Calculate from positive/negative
        positive_count = sum(1 for f in feedbacks if f.is_positive())
        feedback_score = positive_count / len(feedbacks)
        
        # Combined
        return (rating_score + feedback_score) / 2.0
    
    def get_improvement_areas(self, min_feedback_count: int = 3) -> List[str]:
        """Identify areas for improvement based on feedback.
        
        Args:
            min_feedback_count: Minimum feedback to consider
            
        Returns:
            List of improvement areas
        """
        improvements = []
        
        for decision_id, feedbacks in self.decision_feedbacks.items():
            if len(feedbacks) < min_feedback_count:
                continue
            
            quality_score = self.get_decision_quality_score(decision_id)
            
            # Areas with low quality
            if quality_score < 0.5:
                improvements.append(f"Decision {decision_id} has low quality ({quality_score:.2f})")
            
            # Collect suggestions
            suggestions = [f.suggested_action for f in feedbacks if f.suggested_action]
            if suggestions and len(suggestions) >= 2:
                improvements.append(f"Multiple suggestions for {decision_id}")
        
        return improvements
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        total_feedbacks = len(self.feedbacks)
        
        positive_count = sum(
            1 for f in self.feedbacks.values() if f.is_positive()
        )
        
        avg_rating = 0.0
        ratings = [f.rating for f in self.feedbacks.values() if f.rating is not None]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
        
        feedback_types = {}
        for f in self.feedbacks.values():
            ft = f.feedback_type.value
            feedback_types[ft] = feedback_types.get(ft, 0) + 1
        
        return {
            "total_feedbacks": total_feedbacks,
            "positive_count": positive_count,
            "negative_count": total_feedbacks - positive_count,
            "positive_ratio": positive_count / total_feedbacks if total_feedbacks > 0 else 0,
            "avg_rating": round(avg_rating, 2),
            "feedback_types": feedback_types,
            "unique_decisions": len(self.decision_feedbacks),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_feedbacks": len(self.feedbacks),
            "unique_decisions": len(self.decision_feedbacks),
            "statistics": self.get_statistics(),
        }
