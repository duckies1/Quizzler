from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import pytz

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # Calculated based on score and time
    updated_at = Column(DateTime, default=lambda: datetime.now(IST))

    # Enforce one rating per user per trivia quiz
    __table_args__ = (
        UniqueConstraint('quiz_id', 'user_id', name='unique_quiz_user_rating'),
    )

    # Relationships
    quiz = relationship("Quiz")
    user = relationship("User")

    def __repr__(self):
        return f"<Rating(id={self.id}, quiz_id={self.quiz_id}, user_id={self.user_id}, rating={self.rating})>"