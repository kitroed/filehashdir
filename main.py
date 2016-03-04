import argparse
from file_hash_dir import scan_and_hash_system


def _main():
    """Run the command-line interface."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    args = parser.parse_args()

    scan_and_hash_system(args.verbose)

if __name__ == '__main__':
    _main()