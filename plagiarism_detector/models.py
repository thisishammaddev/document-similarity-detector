from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    role = Column(SQLAlchemyEnum(UserRole), default=UserRole.STUDENT, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    documents = relationship("Document", back_populates="uploader")
    reports_generated = relationship("SimilarityReport", foreign_keys="[SimilarityReport.generated_by_id]", back_populates="generated_by_user")

class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False) # To store the user's original file name
    content_hash = Column(String(64), nullable=False, unique=True) # SHA-256 hash of the content to avoid duplicates
    text_content = Column(Text, nullable=False)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)
    uploader_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    file_type = Column(String(10)) # e.g., txt, pdf, docx

    uploader = relationship("User", back_populates="documents")
    similarity_reports_as_new = relationship("SimilarityReport", foreign_keys="[SimilarityReport.new_document_id]", back_populates="new_document")
    similarity_reports_as_existing = relationship("SimilarityReport", foreign_keys="[SimilarityReport.existing_document_id]", back_populates="existing_document")


class SimilarityReport(Base):
    __tablename__ = 'similarity_reports'

    id = Column(Integer, primary_key=True, index=True)
    new_document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    existing_document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    report_details = Column(Text) # Could be JSON string with matching phrases/sentences
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)
    generated_by_id = Column(Integer, ForeignKey('users.id'), nullable=True) # Optional: if a specific user action triggers this

    new_document = relationship("Document", foreign_keys=[new_document_id], back_populates="similarity_reports_as_new")
    existing_document = relationship("Document", foreign_keys=[existing_document_id], back_populates="similarity_reports_as_existing")
    generated_by_user = relationship("User", foreign_keys=[generated_by_id], back_populates="reports_generated")

# Configuration for the database connection (PostgreSQL)
# The DATABASE_URL will be imported from the main config.py
# This ensures a single source of truth for the database URI.
from config import Config # Import the base Config or a specific one if needed

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI) # Use the URI from config
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # This will create the tables in the database if this script is run directly
    # Be cautious running this in production without migration tools
    print("Creating database tables...")
    create_tables()
    print("Database tables created (if they didn't exist).")