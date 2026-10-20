"""Generate SHA-256 checksums for installer executables."""

import hashlib
import sys
from pathlib import Path


def hash_file(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    out_file = file_path.with_name(f"{file_path.name}.sha256")
    out_file.write_text(digest + "\n", encoding="utf-8")
    return digest


def main() -> None:
    targets = sys.argv[1:]
    if not targets:
        default_dir = Path("installer_output")
        targets = [str(p) for p in default_dir.glob("*.exe")]

    for target in targets:
        path = Path(target)
        if path.is_file():
            digest = hash_file(path)
            print(f"  File:    {path}")
            print(f"  SHA-256: {digest}")
            print(f"  Output:  {path.name}.sha256\n")


if __name__ == "__main__":
    main()
