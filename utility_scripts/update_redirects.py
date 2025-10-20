"""
Update Redirects Script

Automatically updates the `redirects.json` file based on changes in a pull request.
Analyzes PR changes to maintain proper URL redirects when documentation files are
moved or removed.

Behavior:
- Removed files: Adds redirects with "TODO: UPDATE_ME" placeholders for human review
- Renamed files: Creates automatic redirects from old paths to new paths
- Updates existing redirects that pointed to changed files

Usage:
    python utility_scripts/update_redirects.py <PR_NUMBER> <OWNER> <REPO>

Arguments:
    PR_NUMBER    Pull request number to analyze
    OWNER        GitHub repository owner/organization
    REPO         GitHub repository name

Example:
    python utility_scripts/update_redirects.py 42 polkadot-developers polkadot-docs

Remote usage:
    python3 <(curl -s https://raw.githubusercontent.com/papermoonio/workflows/main/utility_scripts/update_redirects.py) 42 polkadot-developers polkadot-docs

Create an alias:
    alias update_redirects='python3 <(curl -s https://raw.githubusercontent.com/papermoonio/workflows/main/utility_scripts/update_redirects.py)'
    update_redirects 42 polkadot-developers polkadot-docs

Alias usage:
    update_redirects 42 polkadot-developers polkadot-docs

Features:
- Automatic redirect generation for renamed and removed files
- Ignores images, js, scripts, run folders and hidden files
- Updates existing redirects pointing to changed files
- Provides detailed statistics and feedback
"""

import json
import sys
from pathlib import Path
import requests

REDIRECTS_FILE = "redirects.json"
IGNORED_FOLDERS = {"images", "js", "scripts", "run"}


def is_ignored(filepath: str) -> bool:
    """Skip hidden files/folders or certain top-level folders."""
    parts = filepath.split("/")
    if any(part.startswith(".") for part in parts):
        return True
    if parts[0] in IGNORED_FOLDERS:
        return True
    return False


def format_path(path: str) -> str:
    """Convert a file path into '/path/to/file/' format (remove .md extension, drop 'index')."""
    path = path.strip()
    if path.endswith(".md"):
        path = path[:-3]
    # If the file is 'index' at the end, drop it
    if path.endswith("index"):
        path = path[: -len("index")].rstrip("/")
    return "/" + path.strip("/") + "/"


def load_redirects():
    if Path(REDIRECTS_FILE).exists():
        with open(REDIRECTS_FILE, "r") as f:
            return json.load(f)
    return {"data": []}


def save_redirects(data):
    data["data"].sort(key=lambda r: r["key"])
    with open(REDIRECTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def fetch_pr_files(owner: str, repo: str, pr_number: str):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    files = []
    page = 1

    while True:
        resp = requests.get(url, params={"page": page, "per_page": 100})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        files.extend(data)
        page += 1
    return files


def add_redirect(existing, key, value):
    """
    Add or update a redirect:
    - If the exact key/value exists, skip.
    - If the key exists but value differs, update value.
    - If key does not exist, add new entry.
    """
    for redirect in existing:
        if redirect["key"] == key:
            if redirect["value"] != value:
                redirect["value"] = value  # update to new value
                return "updated"
            return "skipped"  # exact pair already exists
    existing.append({"key": key, "value": value})
    return "added"


def process_pr(owner: str, repo: str, pr_number: str):
    pr_files = fetch_pr_files(owner, repo, pr_number)
    redirects = load_redirects()
    existing = redirects["data"]

    original_count = len(existing)
    modified_count = 0
    added_count = 0
    added_redirects = []

    for f in pr_files:
        status = f.get("status")
        old_path = f.get("previous_filename")
        new_path = f.get("filename")

        if status not in {"removed", "renamed"}:
            continue  # only care about removed/renamed

        # Skip ignored files
        if new_path and is_ignored(new_path):
            continue
        if old_path and is_ignored(old_path):
            continue

        if status == "removed":
            formatted = format_path(new_path)
            for redirect in existing:
                if redirect["value"] == formatted:
                    redirect["value"] = "TODO: UPDATE_ME"
                    modified_count += 1
            result = add_redirect(existing, formatted, "TODO: UPDATE_ME")
            if result == "added":
                added_redirects.append({"key": formatted, "value": "TODO: UPDATE_ME"})
                added_count += 1
            elif result == "updated":
                modified_count += 1

        elif status == "renamed":
            # Apply format_path to both old and new paths, handles index.md as well
            formatted_old = format_path(old_path)
            formatted_new = format_path(new_path)
            for redirect in existing:
                if redirect["value"] == formatted_old:
                    redirect["value"] = formatted_new
                    modified_count += 1
            result = add_redirect(existing, formatted_old, formatted_new)
            if result == "added":
                added_redirects.append({"key": formatted_old, "value": formatted_new})
                added_count += 1
            elif result == "updated":
                modified_count += 1

    save_redirects(redirects)

    print(f"✅ Redirects updated for PR #{pr_number} in repo {owner}/{repo}")

    print(f"\n🔢 Stats:")
    print(f"Original redirects: {original_count}")
    print(f"Redirects modified: {modified_count}")
    print(f"Redirects added: {added_count}")
    print(f"Total redirects now: {len(redirects['data'])}")

    if added_count > 0:
        print("\n⚠️ Redirects that need attention:")
        for r in added_redirects:
            print(f"key: {r['key']}, value: {r['value']}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/update_redirects.py <PR_NUMBER> <OWNER> <REPO>")
        sys.exit(1)

    pr_number = sys.argv[1]
    owner = sys.argv[2]
    repo = sys.argv[3]

    process_pr(owner, repo, pr_number)
