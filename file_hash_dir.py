"""
The idea here is to throw together a quick
SQLite database to store the hash of all
the files found in a given subdir
"""

import argparse
import datetime
import hashlib
import os
import socket
import sys
from typing import NoReturn, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


# --- Models ---

class Base(DeclarativeBase):
    pass


class File(Base):
    """Database model for storing file information and hash values."""

    __tablename__ = "files"

    full_path: Mapped[str] = mapped_column(String, primary_key=True)
    host: Mapped[str] = mapped_column(String(50))
    md5_hash: Mapped[str] = mapped_column(String(32))
    path: Mapped[Optional[str]] = mapped_column(String)
    size: Mapped[Optional[int]] = mapped_column(Integer)
    filename: Mapped[Optional[str]] = mapped_column(String)
    extension: Mapped[Optional[str]] = mapped_column(String)
    modified: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    can_read: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_checked: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:
        """Return string representation of the File object."""
        return f"<File(Filename='{self.filename}' Hash='{self.md5_hash}')>"

    def __str__(self) -> str:
        """Return string representation of the File object."""
        return f"File: {self.filename} (Hash: {self.md5_hash})"


# --- Utility Functions ---

def get_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file efficiently."""
    with open(file_path, "rb") as f:
        # Python 3.11+ preferred method
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(f, "md5").hexdigest()
            
        digest = hashlib.md5()
        while chunk := f.read(65536):
            digest.update(chunk)
        return digest.hexdigest()


def scan_and_hash_system(path: str, verbose: bool) -> None:
    """Scan and hash files in the system and store in database."""
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "filehashdata.sqlite")
    
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)

    hostname = socket.gethostname()

    # Create session for the entire operation using compact context manager
    with Session(engine) as session:
        for dir_path, _, file_names in os.walk(path):
            files_processed_count = 0
            for file_name in file_names:
                full_path = os.path.join(dir_path, file_name)

                # Skip broken symlinks or special files if needed
                if not os.path.isfile(full_path):
                    continue

                file_obj = File(
                    host=hostname,
                    path=dir_path,
                    filename=file_name,
                    full_path=full_path,
                    extension=os.path.splitext(file_name)[1],
                    last_checked=datetime.datetime.now(),
                    can_read=False,
                )

                try:
                    stat = os.stat(full_path)
                    file_obj.size = stat.st_size
                    file_obj.modified = datetime.datetime.fromtimestamp(stat.st_mtime)
                    file_obj.created = datetime.datetime.fromtimestamp(stat.st_ctime)

                    file_obj.md5_hash = get_file_hash(full_path)
                    
                    file_obj.last_checked = datetime.datetime.now()
                    file_obj.can_read = True

                    if verbose:
                        print(file_obj)

                except (PermissionError, FileNotFoundError, OSError) as e:
                    if verbose:
                        print(f"Error accessing {full_path}: {e}")
                    continue

                session.merge(file_obj)
                files_processed_count += 1

            # Commit changes after each directory
            if files_processed_count > 0:
                session.commit()


def main() -> NoReturn:
    """Run the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Scan and hash files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .
  %(prog)s /path/to/scan -v
        """,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )

    args = parser.parse_args()
    
    try:
        scan_and_hash_system(args.directory, args.verbose)
    except KeyboardInterrupt:
        print("\nScan interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
        
    sys.exit(0)


if __name__ == "__main__":
    main()



