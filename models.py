"""
SQLAlchemy models for file hashing application.

This module defines the database models for storing file information
and their hash values.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class File(Base):
    """Database model for storing file information and hash values."""

    __tablename__ = "files"

    host = Column(String(50), nullable=False)
    full_path = Column(String, primary_key=True)
    md5_hash = Column(String(32), nullable=False)
    path = Column(String)
    size = Column(Integer)
    filename = Column(String)
    extension = Column(String)
    modified = Column(DateTime)
    created = Column(DateTime)
    can_read = Column(Boolean)
    last_checked = Column(DateTime)

    def __repr__(self) -> str:
        """Return string representation of the File object."""
        return f"<File(Filename='{self.filename}' Hash='{self.md5_hash}')>"

    def __str__(self) -> str:
        """Return string representation of the File object."""
        return f"File: {self.filename} (Hash: {self.md5_hash})"
