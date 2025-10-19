from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False)
    question_text = Column(String, nullable=False)
    option_a = Column(String, nullable=False)
    option_b = Column(String, nullable=False)
    option_c = Column(String, nullable=False)
    option_d = Column(String, nullable=False)
    correct_option = Column(String, nullable=False)  # 'a', 'b', 'c', 'd'
    mark = Column(Integer, default=1)

    quiz = relationship("Quiz", back_populates="questions")

    def __repr__(self):
        return f"<Question(id={self.id}, quiz_id={self.quiz_id}, text={self.question_text[:20]})>"