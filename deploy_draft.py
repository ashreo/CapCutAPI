#!/usr/bin/env python3
"""Copy a generated dfd_* draft into CapCut's local drafts directory.

Usage:
    python deploy_draft.py                    # deploy newest dfd_* folder
    python deploy_draft.py dfd_cat_123_abc    # deploy a specific draft
    python deploy_draft.py --name "Neon Test" # friendly name shown in CapCut
    python deploy_draft.py --no-index         # copy only, don't touch the index

Notes:
  * CapCut must be CLOSED. It rewrites root_meta_info.json on exit and will
    clobber anything added while it is running.
  * The generator writes draft_info.json; CapCut 8.x reads draft_content.json.
    This script creates the latter.
  * root_meta_info.json is backed up before modification.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "CapCut", "User Data", "Projects", "com.lveditor.draft",
)
META = os.path.join(DRAFTS_DIR, "root_meta_info.json")


def capcut_running():
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return False
    return "capcut.exe" in out.lower()


def newest_draft():
    candidates = [d for d in glob.glob(os.path.join(HERE, "dfd_*")) if os.path.isdir(d)]
    if not candidates:
        sys.exit("No dfd_* draft folders found. Run save_draft first.")
    return max(candidates, key=os.path.getmtime)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", nargs="?", help="draft id / folder name (default: newest)")
    ap.add_argument("--name", help="name shown in CapCut (default: draft id)")
    ap.add_argument("--no-index", action="store_true",
                    help="copy the folder but do not register it in root_meta_info.json")
    ap.add_argument("--force", action="store_true", help="overwrite an existing draft of the same name")
    args = ap.parse_args()

    if not os.path.isdir(DRAFTS_DIR):
        sys.exit(f"CapCut drafts dir not found: {DRAFTS_DIR}")
    if capcut_running():
        sys.exit("CapCut is running. Close it first, then re-run this script.")

    src = os.path.join(HERE, args.draft) if args.draft else newest_draft()
    if not os.path.isdir(src):
        sys.exit(f"Not a directory: {src}")

    name = args.name or os.path.basename(src)
    dest = os.path.join(DRAFTS_DIR, name)
    if os.path.exists(dest):
        if not args.force:
            sys.exit(f"Destination already exists: {dest}\nUse --force to overwrite.")
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    print(f"copied {os.path.basename(src)} -> {dest}")

    info = os.path.join(dest, "draft_info.json")
    content = os.path.join(dest, "draft_content.json")
    if not os.path.exists(content):
        if not os.path.exists(info):
            sys.exit("Draft has neither draft_info.json nor draft_content.json")
        shutil.copy2(info, content)
        print("created draft_content.json (CapCut 8.x reads this name)")

    if args.no_index:
        print("skipped index registration (--no-index)")
        print(f"\nDone. Open CapCut and look for: {name}")
        return

    meta = json.load(open(META, encoding="utf-8"))
    store = meta.get("all_draft_store", [])
    if not store:
        sys.exit("root_meta_info.json has no existing draft to use as a template; "
                 "re-run with --no-index and check whether CapCut auto-detects it.")

    backup = META + f".bak-{int(time.time())}"
    shutil.copy2(META, backup)
    print(f"backed up index -> {os.path.basename(backup)}")

    fold_path = dest.replace("\\", "/")
    duration = 0
    try:
        duration = json.load(open(content, encoding="utf-8")).get("duration", 0) or 0
    except Exception:
        pass

    now_us = int(time.time() * 1_000_000)
    entry = json.loads(json.dumps(store[0]))  # deep copy, keeps every field CapCut expects
    entry.update({
        "draft_id": str(uuid.uuid4()).upper(),
        "draft_name": name,
        "draft_fold_path": fold_path,
        "draft_json_file": fold_path + "\\draft_content.json",
        "draft_root_path": DRAFTS_DIR.replace("/", "\\"),
        "draft_cover": fold_path + "\\draft_cover.jpg",
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": duration,
        "draft_timeline_materials_size": 0,
        "draft_is_invisible": False,
    })
    for k in list(entry):
        if k.startswith("tm_draft_cloud") or k.startswith("draft_cloud") or k.startswith("pippit"):
            entry[k] = type(entry[k])() if entry[k] is not None else None

    store.insert(0, entry)
    meta["all_draft_store"] = store
    if isinstance(meta.get("draft_ids"), int):
        meta["draft_ids"] = meta["draft_ids"] + 1

    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
    print(f"registered '{name}' in root_meta_info.json ({len(store)} drafts)")
    print(f"\nDone. Open CapCut and look for: {name}")


if __name__ == "__main__":
    main()
