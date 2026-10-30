#!/usr/bin/env python3
"""Verify the vendored Rapfi engine artifacts against pinned SHA-256 sums.

Run after cloning the repo, after updating the engine, and in CI:

    python3 backend/scripts/verify_rapfi.py

Exits non-zero when any artifact is missing or modified.
"""

import hashlib
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENGINE_DIR = BACKEND_DIR / "Rapfi-engine"

EXPECTED_SHA256 = {
    "pbrain-rapfi-linux-clang-sse": "4553babac37221372752b3bf16c225d5818c8e1fdef7e4d777762269a4a5fa03",
    "pbrain-rapfi-macos-apple-silicon": "e851a094351c2e77348aa5ae0c071a38ec06eb01419f4060f6169fc3c56871f1",
    "mix9svqfreestyle_bsmix.bin.lz4": "6bc0d1b0ff8e1d857f7f412923cd458f38f1a435087c91ae71fec3676c23ef62",
    "mix9svqrenju_bs15_black.bin.lz4": "7ab8c974c30da07717ce6a504616a62ac8c981500503f0ced0fadefd3f46c5ec",
    "mix9svqrenju_bs15_white.bin.lz4": "a31f318518d3b5630489054d9eb013fd5353c553999640c2bcfd8d95e6fe4e4e",
    "mix9svqstandard_bs15.bin.lz4": "84334f5db96f45b3e36ebdde06d2259d878ae1eb347b7cf74574ac908b8d9e7d",
    "model210901.bin": "2fa08cb15cf240d9533548c3e011b03d46809f6858362e97ee873d0632aa2015",
    "config.toml": "32b9180c91247541d399ceef62906d5ffeb48e34eb5f261612987633820d5d3c",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failures = 0
    for name, expected in EXPECTED_SHA256.items():
        path = ENGINE_DIR / name
        if not path.is_file():
            print(f"MISSING  {name}")
            failures += 1
            continue
        actual = sha256(path)
        if actual != expected:
            print(f"MISMATCH {name}")
            print(f"  expected {expected}")
            print(f"  actual   {actual}")
            failures += 1
            continue
        print(f"ok       {name}")
    if failures:
        print(
            f"\n{failures} artifact(s) failed verification. "
            "Do not run the engine until the files match the pinned checksums "
            "in backend/Rapfi-engine/README.md.",
            file=sys.stderr,
        )
        return 1
    print(f"\nAll {len(EXPECTED_SHA256)} Rapfi artifacts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
