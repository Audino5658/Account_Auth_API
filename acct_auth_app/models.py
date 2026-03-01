from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# --- DATABASE MODEL ---
class User(Base):
    __tablename__ = "users"

    # user_id is the primary key
    user_id = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    nickname = Column(String, nullable=False)
    comment = Column(String, nullable=True)
    
    # store auth token header for simplicity.
    auth_token = Column(String, unique=True, index=True) 