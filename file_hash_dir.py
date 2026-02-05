"""
The idea here is to throw together a quick
SQLite database to store the hash of all
the files found in a given subdir
"""

import argparse
import curses
import datetime
import hashlib
import multiprocessing
import os
import socket
import sys
import time
from typing import Callable, NoReturn, Optional, Any

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, func, desc
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.engine import Engine


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


def get_db_engine() -> Engine:
    """Create and return the SQLAlchemy engine."""
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "filehashdata.sqlite")
    return create_engine(f"sqlite:///{db_path}", echo=False)


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


def process_file_worker(args: tuple[str, str]) -> dict[str, Any]:
    """
    Worker function for multiprocessing. 
    Args: (dir_path, file_name)
    Returns: Dict with file data or error info.
    """
    dir_path, file_name = args
    full_path = os.path.join(dir_path, file_name)
    
    result = {
        "dir_path": dir_path,
        "filename": file_name,
        "full_path": full_path,
        "extension": os.path.splitext(file_name)[1],
        "error": None
    }

    try:
        # Check if file exists (it was found by os.walk but race conditions happen)
        if not os.path.isfile(full_path):
            return result

        stat = os.stat(full_path)
        result["size"] = stat.st_size
        result["modified"] = stat.st_mtime
        result["created"] = stat.st_ctime
        result["md5_hash"] = get_file_hash(full_path)
        result["success"] = True
        
    except (PermissionError, FileNotFoundError, OSError) as e:
        result["error"] = str(e)
        result["success"] = False
        
    return result


DEFAULT_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".env",
    ".idea",
    ".vscode",
}
DEFAULT_IGNORE_EXTS = {".pyc", ".o", ".tmp", ".swp", ".class"}


def scan_and_hash_system(
    path: str,
    verbose: bool,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> int:
    """
    Scan and hash files in the system and store in database.

    Args:
        path: Directory path to scan
        verbose: Print detailed output to stdout
        progress_callback: Optional function(filename, count) called for each file

    Returns:
        Total number of files processed
    """
    engine = get_db_engine()
    Base.metadata.create_all(engine)

    hostname = socket.gethostname()
    total_processed = 0

    # Generator to yield file tasks
    def file_task_generator():
        for dir_path, dir_names, file_names in os.walk(path):
            # Modify dir_names in-place to skip ignored directories
            dir_names[:] = [d for d in dir_names if d not in DEFAULT_IGNORE_DIRS]
            
            for file_name in file_names:
                _, ext = os.path.splitext(file_name)
                if ext in DEFAULT_IGNORE_EXTS:
                    continue
                yield (dir_path, file_name)

    # Use multiprocessing to speed up hashing
    # Using imap_unordered provides better UI responsiveness by yielding results 
    # as soon as they complete, preventing large files from blocking the stream.
    with Session(engine) as session:
        # We use a multiprocessing.Pool to distribute the work
        with multiprocessing.Pool() as pool:
            
            # Use imap_unordered to process results in completion order (fastest first)
            # rather than submission order. This ensures the UI updates immediately 
            # even if a large file takes a while to hash in the background.
            results = pool.imap_unordered(process_file_worker, file_task_generator(), chunksize=20)
            
            # Process results
            pending_commits = 0
            
            for res in results:
                if not res.get("success"):
                    if res.get("error") and verbose:
                        print(f"Error accessing {res['full_path']}: {res['error']}")
                    continue
                
                # Create DB Object
                file_obj = File(
                    host=hostname,
                    path=res["dir_path"],
                    filename=res["filename"],
                    full_path=res["full_path"],
                    extension=res["extension"],
                    size=res["size"],
                    modified=datetime.datetime.fromtimestamp(res["modified"]),
                    created=datetime.datetime.fromtimestamp(res["created"]),
                    md5_hash=res["md5_hash"],
                    last_checked=datetime.datetime.now(),
                    can_read=True,
                )
                
                if verbose:
                    print(file_obj)
                    
                session.merge(file_obj)
                total_processed += 1
                pending_commits += 1
                
                if progress_callback:
                    progress_callback(res["filename"], total_processed)

                # Commit in batches of 100 to keep transaction size healthy
                if pending_commits >= 100:
                    session.commit()
                    pending_commits = 0

            # Final commit
            if pending_commits > 0:
                session.commit()

    return total_processed


# --- Reporting Functions ---


def get_report_data() -> dict:
    """Query the database for summary statistics."""
    engine = get_db_engine()
    with Session(engine) as session:
        total_files = session.scalar(func.count(File.full_path)) or 0
        total_size = session.scalar(func.sum(File.size)) or 0

        # Largest files
        largest_files = session.query(File).order_by(desc(File.size)).limit(5).all()

        # Duplicate hashes (files with same content)
        # Group by hash, having count > 1
        duplicates_query = (
            session.query(
                File.md5_hash,
                func.count(File.full_path).label("count"),
                func.sum(File.size).label("wasted_size"),
            )
            .group_by(File.md5_hash)
            .having(func.count(File.full_path) > 1)
            .order_by(desc("wasted_size"))
            .limit(5)
        )
        duplicates = duplicates_query.all()

        return {
            "total_files": total_files,
            "total_size": total_size,
            "largest_files": largest_files,
            "duplicates": duplicates,
        }


def get_files_by_hash(md5_hash: str) -> list[File]:
    """Retrieve all files matching a specific hash."""
    engine = get_db_engine()
    with Session(engine) as session:
        return session.query(File).filter(File.md5_hash == md5_hash).all()


def prune_stale_records(verbose: bool = False) -> int:
    """Remove records from database for files that no longer exist on disk."""
    engine = get_db_engine()
    removed_count = 0

    with Session(engine) as session:
        # We must iterate all files to check for existence.
        # For huge DBs, this should be done in batches/yields, but simple approach for now.
        all_files = session.query(File).all()
        for file in all_files:
            if not os.path.exists(file.full_path):
                if verbose:
                    print(f"Removing stale record: {file.full_path}")
                session.delete(file)
                removed_count += 1

        session.commit()
    return removed_count


# --- TUI ---


class TUI:
    def __init__(self):
        self.stdscr = None
        self.height = 0
        self.width = 0

    def start(self):
        curses.wrapper(self._main_loop)

    def _draw_menu(self, selected_idx, options):
        self.stdscr.clear()
        self.stdscr.addstr(
            2, 2, "File Hash Directory - TUI Mode", curses.A_BOLD | curses.A_UNDERLINE
        )

        h, w = self.stdscr.getmaxyx()

        for idx, option in enumerate(options):
            x = 4
            y = 4 + idx
            if idx == selected_idx:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, x, f"> {option}")
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, x, f"  {option}")

        self.stdscr.addstr(
            h - 2, 2, "Use Arrow Keys to Navigate, Enter to Select, 'q' to Quit"
        )
        self.stdscr.refresh()

    def _get_input(self, prompt, y, x):
        curses.echo()
        self.stdscr.addstr(y, x, prompt)
        user_input = self.stdscr.getstr(y, x + len(prompt)).decode("utf-8")
        curses.noecho()
        return user_input

    def _scan_wrapper(self):
        self.stdscr.clear()
        self.stdscr.addstr(2, 2, "Enter directory to scan (default: .): ")
        curses.echo()
        path = self.stdscr.getstr(2, 40).decode("utf-8").strip()
        curses.noecho()

        if not path:
            path = "."

        if not os.path.exists(path):
            self.stdscr.addstr(
                4, 2, f"Error: Path '{path}' does not exist!", curses.color_pair(2)
            )
            self.stdscr.getch()
            return

        self.stdscr.addstr(4, 2, f"Scanning '{path}'... Please wait.", curses.A_BOLD)
        self.stdscr.addstr(6, 2, "Last processed:")
        self.stdscr.addstr(7, 2, "Total files:")
        self.stdscr.refresh()

        start_time = time.time()

        def progress_cb(filename, count):
            # Update UI every 10 files or so to prevent flickering
            if count % 5 == 0:
                h, w = self.stdscr.getmaxyx()
                # Truncate filename if too long
                display_name = (
                    (filename[: w - 20] + "..") if len(filename) > w - 20 else filename
                )
                try:
                    self.stdscr.addstr(6, 18, " " * (w - 20))  # Clear line
                    self.stdscr.addstr(6, 18, display_name)
                    self.stdscr.addstr(7, 15, str(count))
                    self.stdscr.refresh()
                except curses.error:
                    pass

        try:
            total = scan_and_hash_system(
                path, verbose=False, progress_callback=progress_cb
            )
            duration = time.time() - start_time
            self.stdscr.addstr(
                9,
                2,
                f"Scan Complete! Processed {total} files in {duration:.2f}s.",
                curses.color_pair(3),
            )
        except Exception as e:
            self.stdscr.addstr(9, 2, f"Error: {e}", curses.color_pair(2))

        self.stdscr.addstr(11, 2, "Press any key to return...")
        self.stdscr.getch()

    def _prune_wrapper(self):
        self.stdscr.clear()
        self.stdscr.addstr(2, 2, "Pruning Invalid Entries...", curses.A_BOLD)
        self.stdscr.addstr(4, 2, "Checking all database records against filesystem...")
        self.stdscr.refresh()

        try:
            count = prune_stale_records(verbose=False)
            self.stdscr.addstr(
                6,
                2,
                f"Cleanup Complete! Removed {count} stale records.",
                curses.color_pair(3),
            )
        except Exception as e:
            self.stdscr.addstr(6, 2, f"Error: {e}", curses.color_pair(2))

        self.stdscr.addstr(8, 2, "Press any key to return...")
        self.stdscr.getch()

    def _show_duplicate_details(self, md5_hash, count, wasted_size):
        self.stdscr.clear()
        self.stdscr.addstr(1, 2, f"Duplicate Files for Hash: {md5_hash}", curses.A_BOLD)
        sz_mb = wasted_size / (1024 * 1024)
        self.stdscr.addstr(2, 2, f"Count: {count} | Total Size: {sz_mb:.2f} MB")
        self.stdscr.addstr(3, 2, "Loading details...", curses.A_BLINK)
        self.stdscr.refresh()

        try:
            files = get_files_by_hash(md5_hash)
            max_y, max_x = self.stdscr.getmaxyx()

            # Use pad for scrolling list
            pad_height = max(len(files) + 5, max_y)
            pad = curses.newpad(pad_height, max_x)

            pad.addstr(0, 0, f"Files ({len(files)}):", curses.A_UNDERLINE)
            for i, f in enumerate(files):
                # Ensure we don't write past pad_height
                if 2 + i < pad_height:
                    pad.addstr(2 + i, 2, f"{i+1}. {f.full_path}")

            # Simple scroll loop
            scroll_y = 0
            while True:
                # Clear content area safely by re-calculating view
                view_height = max_y - 6  # Reserve top 4 + bottom 2

                # Refresh pad onto screen
                # pminrow, pmincol, sminrow, smincol, smaxrow, smaxcol
                try:
                    pad.refresh(scroll_y, 0, 4, 1, max_y - 2, max_x - 2)
                except curses.error:
                    pass

                self.stdscr.addstr(
                    max_y - 1, 2, "Use Arrow Keys to Scroll. 'q' or 'Esc' to Return."
                )
                self.stdscr.refresh()

                key = self.stdscr.getch()
                if key == ord("q") or key == 27:  # Esc or q
                    break
                elif key == curses.KEY_DOWN:
                    if scroll_y < len(files) - view_height + 5:
                        scroll_y += 1
                elif key == curses.KEY_UP:
                    if scroll_y > 0:
                        scroll_y -= 1

        except Exception as e:
            self.stdscr.addstr(
                5, 2, f"Error fetching details: {e}", curses.color_pair(2)
            )
            self.stdscr.getch()

    def _show_report(self):
        self.stdscr.clear()
        self.stdscr.addstr(1, 2, "Loading Report...", curses.A_BLINK)
        self.stdscr.refresh()

        try:
            data = get_report_data()
            max_y, max_x = self.stdscr.getmaxyx()

            selected_dup_idx = 0

            while True:
                self.stdscr.clear()
                self.stdscr.addstr(1, 2, "Database Report", curses.A_BOLD)

                self.stdscr.addstr(3, 2, f"Total Files Stored: {data['total_files']}")

                size_mb = data["total_size"] / (1024 * 1024)
                self.stdscr.addstr(4, 2, f"Total Size tracked: {size_mb:.2f} MB")

                row = 6
                self.stdscr.addstr(
                    row, 2, "--- Top 5 Largest Files ---", curses.A_UNDERLINE
                )
                row += 1
                for f in data["largest_files"]:
                    sz_mb = (f.size or 0) / (1024 * 1024)
                    self.stdscr.addstr(row, 4, f"{f.filename} ({sz_mb:.2f} MB)")
                    row += 1

                row += 1
                self.stdscr.addstr(
                    row,
                    2,
                    "--- Top 5 Duplicate Hashes (Select to view details) ---",
                    curses.A_UNDERLINE,
                )
                row += 1

                duplicate_start_row = row
                if data["duplicates"]:
                    for idx, d in enumerate(data["duplicates"]):
                        # d is (md5_hash, count, wasted_size)
                        wasted_mb = (d[2] or 0) / (1024 * 1024)

                        prefix = " > " if idx == selected_dup_idx else "   "
                        attr = (
                            curses.color_pair(1)
                            if idx == selected_dup_idx
                            else curses.A_NORMAL
                        )

                        text = f"{prefix}Hash {d[0]}... : {d[1]} copies ({wasted_mb:.2f} MB total)"
                        self.stdscr.addstr(row, 2, text, attr)
                        row += 1
                else:
                    self.stdscr.addstr(row, 4, "No complete duplicates found.")

                self.stdscr.addstr(
                    max_y - 2,
                    2,
                    "Arrow Up/Down to select duplicates. Enter to view details. 'q' to return.",
                )

                key = self.stdscr.getch()

                if key == ord("q"):
                    break
                elif key == curses.KEY_UP:
                    if selected_dup_idx > 0:
                        selected_dup_idx -= 1
                elif key == curses.KEY_DOWN:
                    if selected_dup_idx < len(data["duplicates"]) - 1:
                        selected_dup_idx += 1
                elif key == ord("\n"):
                    if data["duplicates"]:
                        sel = data["duplicates"][selected_dup_idx]
                        # sel: (md5_hash, count, wasted_size)
                        self._show_duplicate_details(sel[0], sel[1], sel[2])

        except Exception as e:
            self.stdscr.addstr(
                3, 2, f"Error generating report: {e}", curses.color_pair(2)
            )
            self.stdscr.addstr(5, 2, "Press any key to return...")
            self.stdscr.getch()

    def _main_loop(self, stdscr):
        self.stdscr = stdscr
        # Clear screen
        self.stdscr.clear()

        # Turn off cursor blinking
        curses.curs_set(0)

        # Colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Highlight
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)  # Error
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Success

        options = [
            "Scan Directory",
            "View Database Report",
            "Prune Invalid Entries",
            "Exit",
        ]
        current_row = 0

        while True:
            self._draw_menu(current_row, options)
            key = self.stdscr.getch()

            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(options) - 1:
                current_row += 1
            elif key == ord("\n"):
                if current_row == 0:
                    self._scan_wrapper()
                elif current_row == 1:
                    self._show_report()
                elif current_row == 2:
                    self._prune_wrapper()
                elif current_row == 3:
                    break
            elif key == ord("q"):
                break


def main() -> NoReturn:
    """Run the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Scan and hash files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --ui           # Run in interactive TUI mode
  %(prog)s .              # Scan current directory
  %(prog)s /path/to/scan -v
        """,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory, ignored in UI mode)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )
    parser.add_argument(
        "--ui", action="store_true", help="Launch interactive Terminal User Interface"
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove database records for files that no longer exist",
    )

    args = parser.parse_args()

    if args.ui:
        try:
            tui = TUI()
            tui.start()
            sys.exit(0)
        except Exception as e:
            print(f"UI Error: {e}")
            sys.exit(1)

    if args.prune:
        count = prune_stale_records(verbose=args.verbose)
        print(f"Pruned {count} stale records from database.")
        sys.exit(0)

    try:
        count = scan_and_hash_system(args.directory, args.verbose)
        print(f"Scan complete. Processed {count} files.")
    except KeyboardInterrupt:
        print("\nScan interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
