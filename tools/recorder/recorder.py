"""
Recorder - A High-Performance, Thread-Safe JSONL Logger for Python.

Key Features:
- Zero-Leak Thread Local Storage (TLS): Isolate state per thread without memory leaks.
- Smart Deduplication: Automatically suppresses consecutive duplicate logs per thread.
- Dynamic Frame Climbing: Accurately identifies caller filename and line number
  regardless of direct call `rec("msg")` or `rec.write("msg")`.
- Auto-Adaptive Context: Automatically captures source code lines (`linecache`) when
  exceptions or missing messages occur.
- Non-blocking Disk Sync: Optimized file buffering with optional manual rotation/disk sync.
"""
# ========== ========== ==========


from .helpers import (
    get_signature,
    get_header,
    locked,
    TIME_FORMAT, ENCODING
)

from pathlib import Path
from datetime import datetime
from typing import Self
import threading
import linecache
import sys
import json

MB = 1024 * 1024
BASE_DEPTH = 1
# ========== ========== ==========


class Recorder:
    def __init__(
        self,
        filepath: str | Path,
        max_size: int = 10 * MB,
        context_window: int = 0,
        depth: int = 0,
        auto_adapt: bool = True,
        _print: bool = False,
        sync_disk: bool = False
    ) -> None:
        self.filepath = Path(filepath)
        self.max_size = max_size

        self.context_window = context_window
        self.depth = depth
        self.auto_adapt = auto_adapt

        self._print = _print
        self.sync_disk = sync_disk

        self.file = None
        self.current_size = 0
        self.recording = True
        self.lock = threading.RLock()

        self.local = threading.local()
        # ========== ========== ==========

    def __call__(self, msg: object = None) -> dict:
        return self.write(msg)

    @locked
    def __enter__(self) -> Self:
        if self.file is None:
            self.start()
        return self

    @locked
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.join()
        return False

    def _close_file(self) -> None:
        if self.file and not self.file.closed:
            self.file.flush()
            self.file.close()
            self.file = None

    def _emit(self, record: dict, force_flush: bool = False) -> None:
        if not self.file or self.file.closed:
            return

        line = json.dumps(record, ensure_ascii=False) + "\n"
        line_bytes = line.encode(ENCODING)

        if self.current_size + len(line_bytes) > self.max_size:
            self.rotate()

        self.file.write(line)
        self.current_size += len(line_bytes)

        if self._print:
            print(line, end="")

        if force_flush or self.sync_disk:
            self.file.flush()
    # ========== ========== ==========


    @locked
    def start(self) -> None:
        if self.file and not self.file.closed:
            return

        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.filepath.exists() or self.filepath.stat().st_size == 0

        try:
            self.file = open(self.filepath, "a", encoding=ENCODING)
            if is_new:
                self._emit(get_header(), force_flush=True)
            else:
                self.current_size = self.filepath.stat().st_size

            self.recording = True
        except Exception as e:
            sys.stderr.write(f"[Recorder Error] Failed to start log file: {e}\n")
            self.file = None

    @locked
    def rotate(self) -> None:
        self._close_file()

        if self.filepath.exists():
            now_str = datetime.now().strftime(TIME_FORMAT)
            rotated_path = self.filepath.with_name(f"{self.filepath.stem}_{now_str}{self.filepath.suffix}")
            self.filepath.rename(rotated_path)

        self.current_size = 0
        self.start()

    @locked
    def join(self) -> None:
        pending = getattr(self.local, "pending", None)
        has_repeated = getattr(self.local, "has_repeated", False)

        if pending is not None and has_repeated:
            self._emit(pending, force_flush=True)

        self.local.pending = None
        self.local.has_repeated = False

        self._close_file()
        self.recording = False
    # ========== ========== ==========


    def write(self, msg: object = None) -> dict:
        if not self.recording:
            return {}

        if self.file is None:
            self.start()

        record = self._build_record(msg)
        return self._write_record(record)
    # ========== ==========

    def _get_caller_frame(self):
        frame = sys._getframe(1)
        own_filename = self._get_caller_frame.__code__.co_filename

        while frame and frame.f_code.co_filename == own_filename:
            frame = frame.f_back

        for _ in range(self.depth):
            if frame and frame.f_back:
                frame = frame.f_back

        return frame


    def _build_record(self, msg: object = None) -> dict:
        now_str = datetime.now().strftime(TIME_FORMAT)
        record = {"ts": now_str}

        is_exception = isinstance(msg, Exception)

        if msg is not None:
            if is_exception:
                record["payload"] = f"{type(msg).__name__}: {msg}"
            else:
                record["payload"] = str(msg)

        need_loc = (self.depth > 0) or (self.auto_adapt and (msg is None or is_exception))
        need_ctx = (self.context_window > 0) or (self.auto_adapt and is_exception)

        if need_loc or need_ctx:
            frame = self._get_caller_frame()
            if frame:
                fp, line = frame.f_code.co_filename, frame.f_lineno

                if need_loc:
                    record["loc"] = {"file": Path(fp).name, "func": frame.f_code.co_name, "line": line}

                if need_ctx:
                    measured_ctx_w = (self.context_window if self.context_window > 0 else (2 if is_exception else 0))
                    if measured_ctx_w > 0:
                        start = max(1, line - measured_ctx_w)
                        lines = [linecache.getline(fp, i).rstrip() for i in range(start, line + measured_ctx_w + 1)]
                        linecache.clearcache()
                        if any(lines):
                            record["ctx"] = {"start": start, "lines": lines}
        return record


    @locked
    def _write_record(self, record: dict) -> dict:
        if not record:
            return {}

        current_sig = get_signature(record)

        pending = getattr(self.local, "pending", None)
        has_repeated = getattr(self.local, "has_repeated", False)

        if pending is not None:
            pending_sig = get_signature(pending)

            if current_sig == pending_sig:
                pending["ts"] = record["ts"]
                self.local.has_repeated = True
                return pending

            if has_repeated:
                self._emit(pending)
                self.local.has_repeated = False

        self._emit(record)
        self.local.pending = record
        return record
    # ========== ========== ==========
