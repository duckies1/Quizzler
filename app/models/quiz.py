from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import pytz

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True)  # UUID or generated code
    title = Column(String, nullable=False)  # Quiz name
    description = Column(String, nullable=True)
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    is_trivia = Column(Boolean, default=False)
    topic = Column(String, nullable=True)  # Tag/genre for trivia, null for private
    start_time = Column(DateTime, nullable=True, default=lambda: datetime.now(IST))
    end_time = Column(DateTime, nullable=True, default=lambda: datetime.now(IST))
    duration = Column(Integer, nullable=False)  # In minutes
    positive_mark = Column(Integer, default=1)
    negative_mark = Column(Integer, default=0)
    navigation_type = Column(String, nullable=True)  # 'omni' or 'restricted'
    tab_switch_exit = Column(Boolean, default=True)
    difficulty = Column(String, nullable=True)  # 'easy', 'medium', 'hard' for trivia
    popularity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Add constraint for unique trivia titles per topic
    __table_args__ = (
        UniqueConstraint('title', 'topic', name='unique_trivia_title_topic'),
    )

    # Relationships
    creator = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    sessions = relationship("QuizSession", back_populates="quiz")
    responses = relationship("Response", back_populates="quiz")

    def __repr__(self):
        return f"<Quiz(id={self.id}, title={self.title}, is_trivia={self.is_trivia})>"