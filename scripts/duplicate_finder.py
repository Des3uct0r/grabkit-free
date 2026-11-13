#!/usr/bin/env python3
"""Find duplicate files in a folder tree by size, then by SHA-256 hash.

Usage examples:
  python duplicate_finder.py C:\\Users\\me\\Documents
  python duplicate_finder.py C:\\Users\\me\\Documents --report dup_report.txt
  python duplicate_finder.py C:\\Users\\me\\Documents --delete

Safe by default: duplicates are only LISTED. Nothing is deleted unless you
pass --delete AND type 'yes' when prompted. Groups keep the first file
(sorted by path) and delete the rest.
"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path

# Exit codes: 0 = success, 1 = error, 2 = user backed out of deletion.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CANCELLED = 2

# Read files in 1 MB chunks so huge files don't use up all memory.
CHUNK_SIZE = 1024 * 1024


def sha256_of(path):
    """Compute the SHA-256 hash of a file, reading it in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(folder):
    """Return a list of all regular files under `folder` (any depth)."""
    files = []
    for root, dirs, names in os.walk(folder):
        # Do not follow into symlinked folders; keep the walk local and safe.
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in names:
            path = Path(root) / name
            try:
                if path.is_file():
                    files.append(path)
            except OSError:
                # Unreadable/unusual entries: skip quietly.
                continue
    return files


def find_duplicate_groups(files):
    """Find groups of identical files.

    Speed trick: only hash files whose size is shared with another file.
    Returns a list of groups; each group is a list of paths sorted by name.
    """
    # Step 1: bucket files by size - singletons can't be duplicates.
    by_size = defaultdict(list)
    for path in files:
        try:
            by_size[path.stat().st_size].append(path)
        except OSError:
            continue
    candidates = [paths for paths in by_size.values() if len(paths) > 1]

    # Step 2: hash the remaining candidates and bucket by hash.
    by_hash = defaultdict(list)
    for paths in candidates:
        for path in paths:
            try:
                by_hash[sha256_of(path)].append(path)
            except OSError as exc:
                print("  Could not read {}: {}".format(path, exc))
    groups = []
    for paths in by_hash.values():
        if len(paths) > 1:
            groups.append(sorted(paths, key=lambda p: str(p).lower()))
    # Groups in a stable order: biggest file size first.
    groups.sort(key=lambda g: -g[0].stat().st_size)
    return groups


def human_size(nbytes):
    """Format a byte count as a human-readable string, e.g. 1.4 MB."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return "{:.1f} {}".format(nbytes, unit) if unit != "B" else "{} B".format(nbytes)
        nbytes /= 1024.0
    return "{:.1f} PB".format(nbytes)


def delete_duplicates(groups, yes_confirmed):
    """Delete all but the first file of each group. Returns (deleted, freed)."""
    if not yes_confirmed:
        answer = input("Type 'yes' to DELETE the duplicates listed above (anything "
                       "else cancels): ").strip().lower()
        if answer != "yes":
            print("Cancelled - nothing was deleted.")
            return 0, 0, True
    deleted = 0
    freed = 0
    failed = 0
    for group in groups:
        keeper = group[0]
        for path in group[1:]:
            try:
                size = path.stat().st_size
                path.unlink()
                deleted += 1
                freed += size
                print("Deleted: {} (kept {})".format(path, keeper))
            except OSError as exc:
                failed += 1
                print("Could not delete {}: {}".format(path, exc))
    print("\nDeleted {} file(s), freed {}.".format(deleted, human_size(freed)))
    if failed:
        print("{} file(s) could not be deleted.".format(failed))
    return deleted, freed, False


def main():
    parser = argparse.ArgumentParser(
        description="Find (and optionally delete) duplicate files in a folder tree."
    )
    parser.add_argument("folder", help="Folder to scan, e.g. C:\\Users\\me\\Documents")
    parser.add_argument("--delete", action="store_true",
                        help="Delete duplicates (keeps the first of each group). "
                             "You will be asked to type 'yes' first.")
    parser.add_argument("--report", metavar="FILE",
                        help="Also write a plain-text report to FILE")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print("Folder not found: {}".format(folder))
        return EXIT_ERROR
    if not folder.is_dir():
        print("Not a folder: {}".format(folder))
        return EXIT_ERROR

    print("Scanning {} ...".format(folder))
    files = collect_files(folder)
    print("Found {} file(s). Checking sizes, then hashing candidates ...".format(len(files)))

    groups = find_duplicate_groups(files)

    if not groups:
        print("No duplicate files found. Nice and clean!")
        return EXIT_OK

    total_wasted = sum(p.stat().st_size for g in groups for p in g[1:])
    print("\nFound {} duplicate group(s), {} of wasted space:\n".format(
        len(groups), human_size(total_wasted)))

    report_lines = ["Duplicate file report", "Folder: {}".format(folder), ""]
    for number, group in enumerate(groups, start=1):
        size = group[0].stat().st_size
        header = ("Group {} - {} copies of {}, {} each".format(
            number, len(group), human_size(size), human_size(size)))
        print(header)
        report_lines.append(header)
        for index, path in enumerate(group):
            # Mark the file that would be kept by --delete.
            tag = " [KEEP]" if index == 0 else " [COPY]"
            line = "  {}{}".format(path, tag)
            print(line)
            report_lines.append(line)
        print()
        report_lines.append("")

    if args.report:
        try:
            Path(args.report).write_text("\n".join(report_lines), encoding="utf-8")
            print("Report written to: {}".format(args.report))
        except OSError as exc:
            print("Could not write report: {}".format(exc))
            return EXIT_ERROR

    if args.delete:
        _, _, cancelled = delete_duplicates(groups, yes_confirmed=False)
        if cancelled:
            return EXIT_CANCELLED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
