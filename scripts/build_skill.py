#!/usr/bin/env python3
"""Build a complete beyondseo/ upload ZIP from reviewed source, with a SHA-256 sidecar."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from install_skill import bundle_files
from validate_skill import validate


def build(source, output):
    source = Path(source).resolve()
    output = Path(output).expanduser().absolute()
    report = validate(source)
    if output.suffix.lower() != ".zip":
        raise ValueError("Choose an output filename ending in .zip.")
    if output.is_relative_to(source):
        raise ValueError("Keep release archives outside the source folder.")
    checksum = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or output.is_symlink() or checksum.exists() or checksum.is_symlink():
        raise ValueError("Output already exists. Choose a new archive filename.")
    contents = {p.relative_to(source).as_posix(): p.read_bytes() for p in bundle_files(source)}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    contents["beyondseo-install.json"] = (
        json.dumps({"files_sha256": manifest}, indent=2) + "\n"
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            created = True
            for name, data in sorted(contents.items()):
                item = zipfile.ZipInfo("beyondseo/" + name, date_time=(2020, 1, 1, 0, 0, 0))
                item.create_system = 3
                item.external_attr = 0o100644 << 16
                item.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(item, data)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        with checksum.open("x", encoding="utf-8") as stream:
            stream.write(f"{digest}  {output.name}\n")
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {**report, "archive": str(output), "sha256": digest, "archive_root": "beyondseo/"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(Path(__file__).resolve().parents[1], args.out), indent=2))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(2, f"Packaging stopped: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
