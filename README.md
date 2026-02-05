# File Hash Directory Scanner

A robust, high-performance Python utility to recursively scan directories, calculate MD5 hashes of files, and store the metadata in a SQLite database. Originally written in 2016 and modernized for 2026.

## Features

- **High Performance**: Uses multiprocessing to hash files in parallel, utilizing all available CPU cores.
- **Efficient & Safe**: Uses streaming file reads to handle massive files (ISOs, videos) with minimal memory usage.
- **Interactive TUI**: Includes a Curses-based Terminal User Interface for monitoring scans and browsing reports.
- **Deduplication Analysis**: Reports on duplicate files (by content hash) and wasted space.
- **Smart Filtering**: Automatically ignores common junk directories (`node_modules`, `.git`, `venv`, etc.) and binary artifacts.
- **Resilient**: Tracks file metadata (size, creation/modification dates) and handles permission errors gracefully.
- **Database Backed**: Stores all data in a local `filehashdata.sqlite` file using SQLAlchemy.

## Requirements

- Python 3.11+
- SQLAlchemy 2.0+

## Installation

1. Clone the repository or copy the script.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: On Windows, you may need to install `windows-curses` if you want to use the UI)*

## Usage

### Interactive Mode (Recommended)

Launch the Terminal User Interface to scan, monitor progress, and view reports interactively.

```bash
python file_hash_dir.py --ui
```

### Command Line Mode

Scan the current directory:
```bash
python file_hash_dir.py
```

Scan a specific directory with verbose output:
```bash
python file_hash_dir.py /path/to/media/collection -v
```

Prune stale records (remove database entries for files that no longer exist):
```bash
python file_hash_dir.py --prune
```

### Database Reports

You can view reports via the TUI (`--ui`), which provides:
- Total file count and size.
- Top 5 largest files.
- Top 5 duplicate groups (files with identical content), including potential wasted space.
- Interactive drill-down to see exact paths of duplicate files.

## Configuration (.filehashignore)

The tool has built-in defaults to ignore common directories (like `.git`) and extensions (like `.pyc`). You can override or extend this by creating a `.filehashignore` file in the directory you are scanning.

**Example `.filehashignore`:**
```text
# Ignore build folders
build
dist
target

# Ignore large media/archives
.iso
.mkv
.zip
```
