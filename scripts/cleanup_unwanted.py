"""
Safely move unwanted Dice-related output files into a timestamped archive folder.
Run: python scripts/cleanup_unwanted.py
"""
import shutil
import os
import glob
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATTERNS = [
    "dice_*.txt",
    "*_dry_run*.txt",
    "inspection_output*.txt",
    "dice_*.html",
    "dice_verify*.txt",
    "dice_results_page*.html",
    "dice_home*.html",
    "dice_inspection_log*.txt",
]

def make_archive_dir(root):
    base = os.path.join(root, "cleanup_archive")
    if not os.path.exists(base):
        os.makedirs(base)
        return base
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{base}_{ts}"
    os.makedirs(path, exist_ok=True)
    return path

def find_matches(root, patterns):
    matches = set()
    for p in patterns:
        for path in glob.glob(os.path.join(root, p)):
            if os.path.isfile(path):
                matches.add(os.path.abspath(path))
    return sorted(matches)

def archive_files(files, archive_dir):
    moved = []
    for f in files:
        try:
            dest = os.path.join(archive_dir, os.path.basename(f))
            if os.path.exists(dest):
                name, ext = os.path.splitext(dest)
                dest = f"{name}_{int(datetime.now().timestamp())}{ext}"
            shutil.move(f, dest)
            moved.append((f, dest))
        except Exception as e:
            print(f"Failed to move {f}: {e}")
    return moved

def main():
    print(f"Scanning repository root: {ROOT}")
    matches = find_matches(ROOT, PATTERNS)
    if not matches:
        print("No matching files found.")
        return
    print(f"Found {len(matches)} files to archive:")
    for m in matches:
        print(" -", os.path.relpath(m, ROOT))
    archive_dir = make_archive_dir(ROOT)
    moved = archive_files(matches, archive_dir)
    print(f"Archived {len(moved)} files to {os.path.relpath(archive_dir, ROOT)}")
    for src, dst in moved:
        print(f" {os.path.relpath(src, ROOT)} -> {os.path.relpath(dst, ROOT)}")

if __name__ == '__main__':
    main()
"""
Safely move unwanted Dice-related output files into a timestamped archive folder.
Run: python scripts/cleanup_unwanted.py
"""
import shutil
import os
import glob
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATTERNS = [
    "dice_*.txt",
    "*_dry_run*.txt",
    "inspection_output*.txt",
    "dice_*.html",
    "dice_*.txt",
    "dice_verify*.txt",
    "dice_results_page*.html",
    "dice_home*.html",
    "dice_inspection_log*.txt",
]

def make_archive_dir(root):
    base = os.path.join(root, "cleanup_archive")
    if not os.path.exists(base):
        os.makedirs(base)
        return base
    # if exists, create timestamped
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{base}_{ts}"
    os.makedirs(path, exist_ok=True)
    return path


def find_matches(root, patterns):
    matches = set()
    for p in patterns:
        for path in glob.glob(os.path.join(root, p)):
            # skip directories
            if os.path.isfile(path):
                matches.add(os.path.abspath(path))
    return sorted(matches)


def archive_files(files, archive_dir):
    moved = []
    for f in files:
        try:
            dest = os.path.join(archive_dir, os.path.basename(f))
            # if dest exists, add suffix
            if os.path.exists(dest):
                name, ext = os.path.splitext(dest)
                dest = f"{name}_{int(datetime.now().timestamp())}{ext}"
            shutil.move(f, dest)
            moved.append((f, dest))
        except Exception as e:
            print(f"Failed to move {f}: {e}")
    return moved


def main():
    print(f"Scanning repository root: {ROOT}")
    matches = find_matches(ROOT, PATTERNS)
    if not matches:
        print("No matching files found.")
        return
    print(f"Found {len(matches)} files to archive:")
    for m in matches:
        print(" -", os.path.relpath(m, ROOT))
    archive_dir = make_archive_dir(ROOT)
    moved = archive_files(matches, archive_dir)
    print(f"Archived {len(moved)} files to {os.path.relpath(archive_dir, ROOT)}")
    for src, dst in moved:
        print(f" {os.path.relpath(src, ROOT)} -> {os.path.relpath(dst, ROOT)}")

if __name__ == '__main__':
    main()
