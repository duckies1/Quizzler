from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import pytz

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(IST))
    ended_at = Column(DateTime, nullable=True)
    ended = Column(Boolean, default=False)

    # Enforce one attempt per user per quiz
    __table_args__ = (
        UniqueConstraint('quiz_id', 'user_id', name='unique_quiz_user_session'),
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="sessions")
    user = relationship("User")

    def __repr__(self):
        return f"<QuizSession(id={self.id}, quiz_id={self.quiz_id}, user_id={self.user_id})>"