"""Assemble the public planner bundle for a free serverless host (ADR-011, rules R19 and R20).

    python scripts/build_deploy.py --make-data     # tar the serving store (GEO_SERVING_DIR) and record its SHA-256 in deploy/
    python scripts/build_deploy.py [--data build/serving_data.tar.gz] [--out build/next-site-planner]

The serving store (≈ 98 MB, mostly the 6.4 million-hexagon table) is too large for git, so it travels as a release asset
whose SHA-256 is committed in deploy/serving_data.sha256 and checked here. The bundle holds the serving code, the config,
the store and seven dependencies (no pyarrow, no model files, no API key). `app.py` is the Vercel entrypoint.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "build" / "serving_data.tar.gz"
SHA = ROOT / "deploy" / "serving_data.sha256"
SERVING = ["__init__.py", "contracts.py", "mcp_server.py", "notes.py", "public.py", "store.py", "tools.py"]
FILES = ["countries.json", "hexes.parquet", "plans.parquet", "notes_cache.json"]
REQUIREMENTS = "fastapi==0.143.0\nmcp==2.3.0\npydantic>=2.8\npyyaml>=6.0\nduckdb==1.5.6\nh3==4.5.0\npandas==3.0.6\n"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_data() -> None:
    src = Path(os.environ.get("GEO_SERVING_DIR") or Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")) / "serving").expanduser()
    DATA.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(DATA, "w:gz") as t:
        for f in FILES:
            info = t.gettarinfo(src / f, arcname=f"serving/{f}"); info.mtime = 0; info.uid = info.gid = 0; info.uname = info.gname = ""
            with (src / f).open("rb") as fh:
                t.addfile(info, fh)
    SHA.write_text(f"{sha256(DATA)}  serving_data.tar.gz\n")
    print(f"{DATA} ({DATA.stat().st_size / 1e6:.1f} MB); SHA-256 in {SHA.relative_to(ROOT)}")


def build(data: Path, out: Path) -> None:
    if sha256(data) != SHA.read_text().split()[0]:
        raise SystemExit("serving data does not match deploy/serving_data.sha256")
    shutil.rmtree(out, ignore_errors=True)
    (out / "src" / "serving").mkdir(parents=True); (out / "configs").mkdir()
    (out / "src" / "__init__.py").write_text("")
    for f in SERVING:
        shutil.copy(ROOT / "src" / "serving" / f, out / "src" / "serving" / f)
    shutil.copy(ROOT / "configs" / "default_config.yaml", out / "configs" / "default_config.yaml")
    with tarfile.open(data) as t:
        t.extractall(out, filter="data")
    (out / "requirements.txt").write_text(REQUIREMENTS)
    (out / "app.py").write_text('"""Vercel entrypoint."""\nimport os\nfrom pathlib import Path\n\n'
                                'os.environ.setdefault("GEO_SERVING_DIR", str(Path(__file__).parent / "serving"))\n'
                                'from src.serving.public import app  # noqa: E402,F401\n')
    (out / ".python-version").write_text("3.12\n")
    print(f"bundle: {out} ({sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-data", action="store_true")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(ROOT / "build" / "next-site-planner"))
    a = ap.parse_args()
    make_data() if a.make_data else build(Path(a.data), Path(a.out))


if __name__ == "__main__":
    main()
