import atexit
import os
import platform
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
BOARD_SIZE = int(os.getenv("RAPFI_BOARD_SIZE", "15"))
TIMEOUT_TURN_MS = int(os.getenv("RAPFI_TIMEOUT_TURN", "1500"))
READ_BUFFER_SECONDS = float(os.getenv("RAPFI_READ_BUFFER_SECONDS", "3"))

COORDINATE_RE = re.compile(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*$")


def _binary_candidates() -> list[str]:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return ["pbrain-rapfi-macos-apple-silicon"]
    if system == "Linux":
        if machine in {"arm64", "aarch64"}:
            return [
                "pbrain-rapfi-linux-arm64",
                "pbrain-rapfi-linux-aarch64",
            ]
        return [
            "pbrain-rapfi-linux-clang-sse",
            "pbrain-rapfi-linux-gcc-sse",
            "pbrain-rapfi-linux-clang-avx2",
            "pbrain-rapfi-linux-gcc-avx2",
        ]
    if system == "Windows":
        return [
            "pbrain-rapfi-windows-sse.exe",
            "pbrain-rapfi-windows-avx2.exe",
        ]
    return []


def find_rapfi_binary() -> Path:
    configured = os.getenv("RAPFI_BINARY", "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
        if path.is_file():
            return path
        raise RuntimeError(f"RAPFI_BINARY 指向的文件不存在：{path}")

    engine_dir = BACKEND_DIR.parent / "Rapfi-engine"
    if not engine_dir.is_dir():
        raise RuntimeError("未安装 Rapfi，请先运行 python backend/setup_rapfi.py")

    files = {path.name: path for path in engine_dir.rglob("pbrain-rapfi*") if path.is_file()}
    for name in _binary_candidates():
        if name in files:
            return files[name]

    raise RuntimeError(
        f"没有适用于 {platform.system()} {platform.machine()} 的 Rapfi 可执行文件"
    )


class RapfiEngine:
    def __init__(self, binary: Path | None = None):
        self.binary = binary or find_rapfi_binary()
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.output: queue.Queue[str] = queue.Queue()

    def _send(self, command: str) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Rapfi 进程未启动")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def _read_line(self, timeout: float) -> str:
        if self.process is None:
            raise RuntimeError("Rapfi 进程未启动")
        try:
            line = self.output.get(timeout=timeout)
        except queue.Empty as exc:
            if self.process.poll() is not None:
                raise RuntimeError("Rapfi 进程意外退出") from exc
            raise RuntimeError("Rapfi 思考超时") from exc
        return line

    def _collect_output(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            self.output.put(line.strip())

    def _read_until_ok(self) -> None:
        deadline = time.monotonic() + READ_BUFFER_SECONDS
        while time.monotonic() < deadline:
            line = self._read_line(max(0.05, deadline - time.monotonic()))
            if line.upper() == "OK":
                return
        raise RuntimeError("Rapfi 启动失败：未返回 OK")

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        self.binary.chmod(self.binary.stat().st_mode | 0o111)
        self.output = queue.Queue()
        self.process = subprocess.Popen(
            [str(self.binary)],
            cwd=str(self.binary.parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        threading.Thread(
            target=self._collect_output,
            args=(self.process,),
            daemon=True,
        ).start()
        self._send(f"START {BOARD_SIZE}")
        self._read_until_ok()
        self._send("INFO rule 0")
        self._send(f"INFO timeout_turn {TIMEOUT_TURN_MS}")

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            if process.poll() is None and process.stdin is not None:
                process.stdin.write("END\n")
                process.stdin.flush()
                process.wait(timeout=1)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            process.kill()

    def restart(self) -> None:
        self.close()
        self.start()

    def _read_best_move(self, timeout_ms: int) -> tuple[int, int]:
        deadline = time.monotonic() + timeout_ms / 1000 + READ_BUFFER_SECONDS
        while time.monotonic() < deadline:
            line = self._read_line(max(0.05, deadline - time.monotonic()))
            match = COORDINATE_RE.match(line)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
                return y, x
        raise RuntimeError("Rapfi 未返回合法坐标")

    def best_move(
        self,
        moves: list[dict],
        timeout_ms: int = TIMEOUT_TURN_MS,
        strength_level: int = 100,
    ) -> tuple[int, int]:
        with self.lock:
            try:
                self.start()
                self._send(f"INFO timeout_turn {timeout_ms}")
                self._send(f"INFO STRENGTH {strength_level}")
                self._send("BOARD")
                for index, move in enumerate(moves):
                    player = 1 if index % 2 == 0 else 2
                    self._send(f"{int(move['col'])},{int(move['row'])},{player}")
                self._send("DONE")
                return self._read_best_move(timeout_ms)
            except Exception:
                self.restart()
                raise


_engine: RapfiEngine | None = None
_engine_lock = threading.Lock()


def get_rapfi_engine() -> RapfiEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = RapfiEngine()
        return _engine


def close_rapfi_engine() -> None:
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.close()
            _engine = None


atexit.register(close_rapfi_engine)
