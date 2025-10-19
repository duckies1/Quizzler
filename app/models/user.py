from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import pytz

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Supabase UID
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

    # Relationships
    quizzes = relationship("Quiz", back_populates="creator")

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"