#!/usr/bin/env python3
"""Sort the files in a folder (e.g. your Downloads folder) into tidy subfolders
by file type: Images, Documents, Audio, Video, Archives, Code, Other.

Usage examples:
  python file_organizer.py C:\\Users\\me\\Downloads --dry-run
  python file_organizer.py C:\\Users\\me\\Downloads
  python file_organizer.py C:\\Users\\me\\Downloads --by-date

Safe by default: use --dry-run first to see what would happen without
moving anything. Files are moved, never deleted.
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Exit codes: 0 = success, 1 = error.
EXIT_OK = 0
EXIT_ERROR = 1

# Built-in extension map: file extension (lowercase, incl. dot) -> category.
CATEGORIES = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff",
        ".svg", ".ico", ".heic", ".raw", ".cr2", ".nef",
    ],
    "Documents": [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
        ".rtf", ".odt", ".ods", ".odp", ".md", ".csv", ".epub", ".html",
        ".htm", ".log",
    ],
    "Audio": [
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".aiff",
    ],
    "Video": [
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
        ".mpg", ".mpeg", ".ts",
    ],
    "Archives": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".tgz",
    ],
    "Code": [
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go",
        ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".json", ".xml",
        ".yml", ".yaml", ".sql", ".ipynb",
    ],
}

# Reverse lookup: ".jpg" -> "Images"
EXT_TO_CATEGORY = {}
for category, exts in CATEGORIES.items():
    for ext in exts:
        EXT_TO_CATEGORY[ext] = category


def category_for(path):
    """Return the category name for a file path (defaults to 'Other')."""
    return EXT_TO_CATEGORY.get(path.suffix.lower(), "Other")


def plan_moves(folder, by_date):
    """Build a list of (source, destination) moves for a folder.

    Returns (moves, errors). 'errors' is a list of (path, reason) tuples.
    Subfolders are never touched; only files directly inside `folder`.
    """
    moves = []
    errors = []
    for item in sorted(folder.iterdir()):
        # Skip anything that is not a regular file (subfolders, shortcuts to
        # folders, etc.). We never organize the organizer's own output.
        if not item.is_file():
            continue
        if by_date:
            # Group by the file's last-modified month, e.g. 2026-11.
            month = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m")
            subdir = month
        else:
            subdir = category_for(item)
        dest = folder / subdir / item.name
        if dest.exists():
            errors.append((item, "destination already exists: {}".format(dest)))
            continue
        moves.append((item, dest))
    return moves, errors


def main():
    parser = argparse.ArgumentParser(
        description="Sort files in a folder into subfolders by type (or month)."
    )
    parser.add_argument("folder", help="Folder to organize, e.g. C:\\Users\\me\\Downloads")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be moved, without moving anything")
    parser.add_argument("--by-date", action="store_true",
                        help="Organize into YYYY-MM month folders instead of type folders")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print("Folder not found: {}".format(folder))
        return EXIT_ERROR
    if not folder.is_dir():
        print("Not a folder: {}".format(folder))
        return EXIT_ERROR

    # Plan everything first, so nothing is moved if the plan fails.
    moves, errors = plan_moves(folder, args.by_date)

    # Print the plan as a table.
    mode = "month" if args.by_date else "type"
    print("Folder: {}".format(folder))
    if args.dry_run:
        print("DRY RUN - nothing will be moved. Plan ({}):".format(mode))
    else:
        print("Plan ({}):".format(mode))

    if not moves and not errors:
        print("  Nothing to organize - this folder is already tidy.")
        return EXIT_OK

    widths = (46, 18)  # column widths for file name and destination folder
    print("  {:<46} {:<18}".format("FILE", "MOVE TO"))
    print("  " + "-" * (sum(widths) + 2))
    for src, dest in moves:
        print("  {:<46} {:<18}".format(
            str(src.name)[:widths[0]], str(dest.parent.relative_to(folder))[:widths[1]]))

    # Report files we could not plan for.
    if errors:
        print("\nSkipped ({}):".format(len(errors)))
        for path, reason in errors:
            print("  {} - {}".format(path.name, reason))

    if args.dry_run:
        print("\nDry run complete: {} file(s) would be moved. "
              "Run again without --dry-run to move them.".format(len(moves)))
        return EXIT_OK

    # Do the actual moves.
    moved = 0
    real_errors = []
    for src, dest in moves:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moved += 1
        except (OSError, shutil.Error) as exc:
            real_errors.append((src, str(exc)))

    print("\nDone: {} file(s) moved.".format(moved))
    if real_errors:
        print("Failed ({}):".format(len(real_errors)))
        for path, reason in real_errors:
            print("  {} - {}".format(path.name, reason))
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
