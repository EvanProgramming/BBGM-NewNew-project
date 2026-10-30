# Rapfi Engine Artifacts

This directory vendors prebuilt binaries and compressed network weights from
the open-source [Rapfi](https://github.com/zc-feng/rapfi) Gomoku/Renju engine.
They are executed as a subprocess by `backend/games/rapfi.py` and are **not
reviewable source** — treat them like any third-party dependency.

## Provenance

| File | Origin | Purpose |
| --- | --- | --- |
| `pbrain-rapfi-linux-clang-sse` | Rapfi release build (Linux, x86-64 SSE) | Engine binary for Linux |
| `pbrain-rapfi-macos-apple-silicon` | Rapfi release build (macOS, arm64) | Engine binary for Apple Silicon Macs |
| `mix9svqstandard_bs15.bin.lz4` | Rapfi model bundle | Standard Gomoku weights, board size 15 |
| `mix9svqfreestyle_bsmix.bin.lz4` | Rapfi model bundle | Freestyle Gomoku weights |
| `mix9svqrenju_bs15_black.bin.lz4` | Rapfi model bundle | Renju weights, black |
| `mix9svqrenju_bs15_white.bin.lz4` | Rapfi model bundle | Renju weights, white |
| `model210901.bin` | Rapfi legacy model | Legacy weights (unused by current code paths) |
| `config.toml` | Rapfi configuration | Engine options (referenced by upstream defaults) |

Before updating any artifact, record the exact upstream commit/tag and re-pin
the SHA-256 in `EXPECTED_SHA256` below.

## Integrity

`backend/scripts/verify_rapfi.py` verifies every artifact against the pinned
checksums. Run it after cloning, after updating the engine, and in CI:

```bash
python3 backend/scripts/verify_rapfi.py
```

Expected SHA-256 (current pins):

```
4553babac37221372752b3bf16c225d5818c8e1fdef7e4d777762269a4a5fa03  pbrain-rapfi-linux-clang-sse
e851a094351c2e77348aa5ae0c071a38ec06eb01419f4060f6169fc3c56871f1  pbrain-rapfi-macos-apple-silicon
6bc0d1b0ff8e1d857f7f412923cd458f38f1a435087c91ae71fec3676c23ef62  mix9svqfreestyle_bsmix.bin.lz4
7ab8c974c30da07717ce6a504616a62ac8c981500503f0ced0fadefd3f46c5ec  mix9svqrenju_bs15_black.bin.lz4
a31f318518d3b5630489054d9eb013fd5353c553999640c2bcfd8d95e6fe4e4e  mix9svqrenju_bs15_white.bin.lz4
84334f5db96f45b3e36ebdde06d2259d878ae1eb347b7cf74574ac908b8d9e7d  mix9svqstandard_bs15.bin.lz4
2fa08cb15cf240d9533548c3e011b03d46809f6858362e97ee873d0632aa2015  model210901.bin
32b9180c91247541d399ceef62906d5ffeb48e34eb5f261612987633820d5d3c  config.toml
```

## Future work

These 40MB of opaque binaries belong outside the source tree. Candidates:

1. **Git LFS** for the large model files.
2. A setup script (see the `backend/setup_rapfi.py` reference in `rapfi.py`
   error messages) that downloads artifacts from pinned upstream URLs and
   verifies the checksums above.
3. Building the engine from source in CI for each deployment platform.

Until one of these lands, do not replace a file without updating the pins in
`backend/scripts/verify_rapfi.py` and this README in the same commit.
