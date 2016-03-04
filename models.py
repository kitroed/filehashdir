
from sqlalchemy import Column, Integer, String, DateTime, Boolean, MetaData

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql.schema import ForeignKey

Base = declarative_base()

# Should make a Host class?


class File(Base):
    __tablename__ = 'files'

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

    def __repr__(self):
        return "<File(Filename='%s' Hash='%s')>" % (self.filename, self.md5_hash)