"""Deploy the hosted demo to a Hugging Face Space.

Stages the Space layout (webdemo/hf/* at the repo root, plus app.py and
static/ from webdemo/) into a temp dir and uploads it in a single commit.

Usage:
    HF_TOKEN=hf_xxx python webdemo/deploy_hf.py [repo_id]

repo_id defaults to "ayushjangid/aeo-audit-demo".
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

WEBDEMO = Path(__file__).parent


def main() -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Set HF_TOKEN (a 'Write' token from hf.co/settings/tokens).")
    repo_id = sys.argv[1] if len(sys.argv) > 1 else "ayushjangid/aeo-audit-demo"

    api = HfApi(token=token)
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for f in (WEBDEMO / "hf").iterdir():
            shutil.copy(f, stage / f.name)
        shutil.copy(WEBDEMO / "app.py", stage / "app.py")
        shutil.copytree(WEBDEMO / "static", stage / "static")

        api.upload_folder(
            folder_path=str(stage),
            repo_id=repo_id,
            repo_type="space",
            commit_message="deploy from aeo-audit repo (webdemo/)",
        )

    owner, name = repo_id.split("/")
    print(f"Uploaded. Space: https://huggingface.co/spaces/{repo_id}")
    print(f"App URL (after build): https://{owner}-{name}.hf.space")


if __name__ == "__main__":
    main()
