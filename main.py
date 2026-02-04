import argparse
from typing import NoReturn

from file_hash_dir import scan_and_hash_system


def main() -> NoReturn:
    """Run the command-line interface."""
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
