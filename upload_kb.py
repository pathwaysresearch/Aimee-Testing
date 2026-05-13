"""
UPLOAD (run once per knowledge-base refresh).
Uploads every .md file under ./my-knowledge-base/ and saves the file IDs so
sessions can mount them without re-uploading.
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

KB_FOLDER = Path("E:\\Internship-Folder\\Prof. Gene\\webapp\\Vault\\raw")
OUTPUT_FILE = Path("aimee_kb_files.json")


def upload_kb(kb_folder: Path = KB_FOLDER) -> list[dict]:
    if not kb_folder.exists():
        raise FileNotFoundError(f"Knowledge-base folder not found: {kb_folder}")

    md_files = sorted(kb_folder.glob("**/*.md"))
    if not md_files:
        print("No .md files found.")
        return []

    uploaded = []
    for md_file in md_files:
        relative_path = md_file.relative_to(kb_folder)
        mount_path = f"/workspace/Aimee-AI/{relative_path.as_posix()}"

        print(f"Uploading {relative_path}…")
        with open(md_file, "rb") as f:
            file = client.beta.files.upload(
                file=(md_file.name, f, "text/markdown"),
            )
        uploaded.append(
            {"type": "file", "file_id": file.id, "mount_path": mount_path}
        )
        print(f"  ✓ {relative_path} → {file.id}")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(uploaded, f, indent=2)
    print(f"\nUploaded {len(uploaded)} files → {OUTPUT_FILE}")
    return uploaded


if __name__ == "__main__":
    upload_kb()
