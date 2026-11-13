#!/usr/bin/env python3
"""Show how much disk space each first-level subfolder of a path uses,
sorted largest first, with a grand total.

Usage examples:
  python folder_size.py C:\\Users\\me
  python folder_size.py C:\\Users\\me\\Downloads --depth 2
  python folder_size.py C:\\Users\\me --files

Read-only: this script never changes anything on disk.
"""

import argparse
import os
import sys
from pathlib import Path

# Exit codes: 0 = success, 1 = error.
EXIT_OK = 0
EXIT_ERROR = 1

NAME_WIDTH = 40  # column width for folder/file names
SIZE_WIDTH = 12  # column width for sizes


def human_size(nbytes):
    """Format a byte count as a human-readable string, e.g. 1.4 MB."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return "{:.1f} {}".format(nbytes, unit) if unit != "B" else "{} B".format(nbytes)
        nbytes /= 1024.0
    return "{:.1f} PB".format(nbytes)


def tree_size(path):
    """Total size in bytes of a file or an entire folder tree.

    Returns (size_in_bytes, error_count). Errors (unreadable files etc.)
    are counted, not raised, so one bad file never stops the scan.
    """
    total = 0
    errors = 0
    if path.is_file():
        try:
            return path.stat().st_size, 0
        except OSError:
            return 0, 1
    try:
        for root, dirs, names in os.walk(path):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for name in names:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    errors += 1
    except OSError:
        errors += 1
    return total, errors


def main():
    parser = argparse.ArgumentParser(
        description="Show the size of each first-level subfolder, largest first."
    )
    parser.add_argument("path", help="Folder to measure, e.g. C:\\Users\\me")
    parser.add_argument("--depth", type=int, default=1, metavar="N",
                        help="How many levels deep to list (default: 1)")
    parser.add_argument("--files", action="store_true",
                        help="Also list the 10 largest files in the tree")
    args = parser.parse_args()

    if args.depth < 1:
        print("--depth must be at least 1")
        return EXIT_ERROR

    root = Path(args.path)
    if not root.exists():
        print("Folder not found: {}".format(root))
        return EXIT_ERROR
    if not root.is_dir():
        print("Not a folder: {}".format(root))
        return EXIT_ERROR

    print("Measuring {} ...".format(root))

    # Collect every subfolder up to --depth levels, with its total size.
    rows = []  # (relative_path_str, size_bytes, is_folder)
    total = 0
    total_errors = 0

    def walk_level(folder, level):
        """Recursively add one row per subfolder at each level up to --depth."""
        nonlocal total_errors
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            print("  Could not read {}: {}".format(folder, exc))
            return
        for entry in entries:
            if entry.is_dir():
                size, errors = tree_size(entry)
                total_errors += errors
                rows.append((str(entry.relative_to(root)), size, True))
                if level + 1 < args.depth:
                    walk_level(entry, level + 1)

    walk_level(root, 0)

    # The grand total is the size of the whole starting folder.
    total, errors = tree_size(root)
    total_errors += errors

    if not rows:
        print("No subfolders found inside {}.".format(root))
        return EXIT_OK

    # Largest first.
    rows.sort(key=lambda r: -r[1])

    print()
    print("{:<{nw}} {:>{sw}}".format("FOLDER", "SIZE", nw=NAME_WIDTH, sw=SIZE_WIDTH))
    print("-" * (NAME_WIDTH + SIZE_WIDTH + 1))
    for rel, size, is_folder in rows:
        indent = "  " * rel.count(os.sep)  # indent deeper levels slightly
        name = indent + (rel.split(os.sep)[-1] or rel)
        print("{:<{nw}} {:>{sw}}".format(
            name[:NAME_WIDTH], human_size(size), nw=NAME_WIDTH, sw=SIZE_WIDTH))

    print("-" * (NAME_WIDTH + SIZE_WIDTH + 1))
    print("{:<{nw}} {:>{sw}}".format(
        "TOTAL for {}".format(root), human_size(total), nw=NAME_WIDTH, sw=SIZE_WIDTH))
    if total_errors:
        print("(Note: {} item(s) could not be read and were skipped.)".format(total_errors))

    # Optional: top 10 largest files anywhere in the tree.
    if args.files:
        big = []  # (size, path)
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(dirpath, d))]
            for name in names:
                path = Path(dirpath) / name
                try:
                    if path.is_file():
                        big.append((path.stat().st_size, path))
                except OSError:
                    continue
        big.sort(key=lambda item: -item[0])
        print("\n10 largest files:")
        print("{:<{nw}} {:>{sw}}".format("FILE", "SIZE", nw=NAME_WIDTH, sw=SIZE_WIDTH))
        for size, path in big[:10]:
            rel = str(path.relative_to(root))
            print("{:<{nw}} {:>{sw}}".format(
                rel[:NAME_WIDTH], human_size(size), nw=NAME_WIDTH, sw=SIZE_WIDTH))
        if not big:
            print("  (No files found.)")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
