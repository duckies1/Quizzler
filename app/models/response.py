from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import pytz

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    answers = Column(JSON, nullable=False)  # {question_id: selected_option or null}
    correct_answers = Column(JSON, nullable=True)  # {question_id: correct_option}
    score = Column(Integer, nullable=True)
    submitted_at = Column(DateTime, default=lambda: datetime.now(IST))

    # Enforce one response per user per quiz
    __table_args__ = (
        UniqueConstraint('quiz_id', 'user_id', name='unique_quiz_user_response'),
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="responses")
    user = relationship("User")

    def __repr__(self):
        return f"<Response(id={self.id}, quiz_id={self.quiz_id}, user_id={self.user_id})>"