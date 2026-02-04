"""
The idea here is to throw together a quick
SQLite database to store the hash of all
the files found in a given subdir
"""

import datetime
import hashlib
import os
import socket
from typing import NoReturn

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import models


def scan_and_hash_system(verbose: bool) -> None:
    """Scan and hash files in the system and store in database."""
    # Use the Base from models.py instead of creating a new one
    Base = models.Base

    basedir = os.path.abspath(os.path.dirname(__file__))

    engine = create_engine(
        f"sqlite:///{os.path.join(basedir, 'filehashdata.sqlite')}", echo=False
    )

    Base.metadata.create_all(engine)

    # Use the new SQLAlchemy 2.0+ sessionmaker syntax
    SessionMaker = sessionmaker(bind=engine)

    path = "/"

    hostname = socket.gethostname()

    # Create session for the entire operation
    session = SessionMaker()
    try:
        for dir_path, dir_names, file_names in os.walk(path):
            for file_name in file_names:
                full_path = os.path.join(dir_path, file_name)

                file = models.File(
                    host=hostname,
                    path=dir_path,
                    filename=file_name,
                    full_path=full_path,
                    extension=os.path.splitext(file_name)[1],
                    last_checked=datetime.datetime.now(),
                    can_read=False,
                )

                try:
                    file.size = os.path.getsize(full_path)
                    file.modified = datetime.datetime.fromtimestamp(
                        os.path.getmtime(full_path)
                    )
                    file.created = datetime.datetime.fromtimestamp(
                        os.path.getctime(full_path)
                    )

                    with open(full_path, "rb") as f:
                        file.md5_hash = hashlib.md5(f.read()).hexdigest()

                    file.last_checked = datetime.datetime.now()
                    file.can_read = True

                    if verbose:
                        print(file)

                except (PermissionError, FileNotFoundError, OSError) as e:
                    print(
                        f"Permission or FileNotFound error when hashing {full_path}: {e}"
                    )
                    continue

                # Use merge with the new session syntax
                session.merge(file)

            # Commit changes after each directory
            session.commit()

    finally:
        session.close()
        # save info to database
        # we'll use merge since the path is unique


def main() -> NoReturn:
    """Run the command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan and hash files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s -v
        """,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )

    args = parser.parse_args()
    scan_and_hash_system(args.verbose)
    # Exit after completing the scan
    exit(0)


if __name__ == "__main__":
    main()
