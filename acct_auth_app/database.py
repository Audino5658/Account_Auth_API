from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- DATABASE SETUP (SQLAlchemy) ---
# using SQLite for simplicity in this test. 

SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
