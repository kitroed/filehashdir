# the idea here is to throw together a quick
# SQLite database to store the hash of all
# the files found in a given subdir

import hashlib
import os
import time
import datetime
import socket
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import models

def scan_and_hash_system(verbose):
    Base = declarative_base()

    basedir = os.path.abspath(os.path.dirname(__file__))

    engine = create_engine('sqlite:///' + os.path.join(basedir, 'filehashdata.sqlite'),
                           echo=False)

    Base.metadata.create_all(engine)

    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()

    path = '/'

    hostname = socket.gethostname()

    for dir_path, dir_names, file_names in os.walk(path):
        for file_name in file_names:
            file = models.File(full_path=os.path.join(dir_path, file_name))

            file.host = hostname
            file.path = dir_path
            file.filename = file_name
            file.extension = os.path.splitext(file_name)[1]
            file.last_checked = datetime.datetime.now()
            file.can_read = False

            try:
                file.size = os.path.getsize(file.full_path)
                file.modified = datetime.datetime.fromtimestamp(os.path.getmtime(file.full_path))
                file.created = datetime.datetime.fromtimestamp(os.path.getctime(file.full_path))
                file.md5_hash = hashlib.md5(open(file.full_path, 'rb').read()).hexdigest()
                file.last_checked = datetime.datetime.now()
                file.can_read = True
                if verbose:
                    print(file)
            except (PermissionError, FileNotFoundError, OSError):
                print("Permission or FileNotFound error when hashing %s" % file.full_path)
                continue

            session.merge(file)
        session.commit()
        # save info to database
        # we'll use merge since the path is unique
