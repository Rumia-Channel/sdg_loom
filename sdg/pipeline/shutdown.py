"""sdg/pipeline/shutdown.py - Graceful shutdown & heartbeat

VPS 等での無人運用を想定した中断体制:

- SIGTERM / SIGINT の graceful shutdown
  シグナル受信 → 新規行の投入を停止 → 完了済み行をフラッシュ → 終了。
  ``--resume`` と組み合わせることで、シグナル後の再起動時に
  未処理行から自動的に再開できる。

- Heartbeat ファイルの定期書き出し
  進捗・PID・ステータスを JSON でアトミックに書き出す。
  外部監視（cron, systemd, Zabbix 等）からファイルの mtime や
  ``status`` フィールドを確認することで、プロセスの生死と
  進捗をリモートから把握できる。
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# ShutdownManager
# ---------------------------------------------------------------------------


class ShutdownManager:
    """SIGTERM / SIGINT を捕捉し、graceful shutdown を調整する。

    Unix では ``loop.add_signal_handler()`` で非同期安全にシグナルを捕捉する。
    Windows では SIGINT は KeyboardInterrupt にフォールバックし、
    SIGTERM のみ ``signal.signal()`` で同期的に捕捉する。

    使い方::

        shutdown = ShutdownManager()

        async def main():
            shutdown.install()
            try:
                async for item in work():
                    ...
                    if shutdown.requested:
                        break
            finally:
                shutdown.uninstall()
    """

    def __init__(self) -> None:
        self._event: Optional[asyncio.Event] = None
        self._reason: Optional[str] = None
        self._installed = False

    # -- public API ----------------------------------------------------------

    @property
    def requested(self) -> bool:
        """シャットダウンが要求されていれば True。"""
        return self._event is not None and self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        """シャットダウン要求の原因 (``SIGTERM`` / ``SIGINT`` / ``manual``)。"""
        return self._reason

    def install(self) -> None:
        """シグナルハンドラを登録する。

        ``asyncio`` イベントループ内で呼び出すこと。
        """
        self._event = asyncio.Event()
        self._installed = True

        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_signal, sig)
        else:
            # Windows: SIGTERM のみ signal.signal() で捕捉。
            # SIGINT は KeyboardInterrupt として伝播され、
            # PipelineEngine.run() の既存ハンドラが処理する。
            signal.signal(signal.SIGTERM, self._handle_signal_sync)

    def uninstall(self) -> None:
        """シグナルハンドラを解除し、デフォルト動作に戻す。"""
        if not self._installed:
            return
        self._installed = False

        if sys.platform != "win32":
            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.remove_signal_handler(sig)
            except RuntimeError:
                pass  # イベントループが既に閉じている
        else:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)

    def request(self, reason: str = "manual") -> None:
        """プログラム側からシャットダウンを要求する。"""
        self._reason = reason
        if self._event is not None:
            self._event.set()

    # -- internal ------------------------------------------------------------

    def _handle_signal(self, sig: signal.Signals) -> None:
        self._reason = signal.Signals(sig).name
        if self._event is not None:
            self._event.set()

    def _handle_signal_sync(self, signum: int, frame: object) -> None:
        self._reason = signal.Signals(signum).name
        if self._event is not None:
            self._event.set()


# ---------------------------------------------------------------------------
# HeartbeatWriter
# ---------------------------------------------------------------------------

_ISO_FMT = "%Y-%m-%dT%H:%M:%S%z"


class HeartbeatWriter:
    """進捗・ステータスを JSON ファイルにアトミック書き出しする。

    外部監視ツールは以下を確認できる:

    - ``updated_at`` / ファイル mtime → プロセスが生存しているか
    - ``status`` → ``running`` / ``completed`` / ``interrupted`` / ``error``
    - ``completed_rows`` / ``total_rows`` → 進捗率
    - ``rows_per_minute`` → 処理速度

    書き込みは ``tempfile`` + ``os.replace()`` によるアトミック操作のため、
    読み手側が不完全な JSON を読むことはない。

    使い方::

        hb = HeartbeatWriter("/var/run/sdg-loom/heartbeat.json", total_rows=10000)
        # 各行処理後:
        hb.update(completed=150, errors=2, concurrency=32)
        # 終了時:
        hb.finalize(completed=10000, errors=5, status="completed")
    """

    def __init__(
        self,
        path: str,
        total_rows: Optional[int] = None,
        interval: float = 10.0,
    ) -> None:
        self._path = path
        self._total_rows = total_rows
        self._interval = interval
        self._start_time = time.monotonic()
        self._start_wall = datetime.now(timezone.utc)
        self._last_write: float = 0.0

        # ディレクトリを事前作成
        dir_name = os.path.dirname(self._path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    # -- public API ----------------------------------------------------------

    def update(
        self,
        completed: int,
        errors: int,
        concurrency: Optional[int] = None,
        force: bool = False,
    ) -> None:
        """ハートビートを更新する。

        前回の書き込みから ``interval`` 秒未満の場合はスキップする
        (``force=True`` で強制書き込み)。
        """
        now = time.monotonic()
        if not force and (now - self._last_write) < self._interval:
            return
        self._last_write = now
        self._write(completed, errors, concurrency, "running")

    def finalize(
        self,
        completed: int,
        errors: int,
        status: str = "completed",
    ) -> None:
        """最終ステータスを書き込む。"""
        self._write(completed, errors, None, status)

    # -- internal ------------------------------------------------------------

    def _write(
        self,
        completed: int,
        errors: int,
        concurrency: Optional[int],
        status: str,
    ) -> None:
        elapsed = time.monotonic() - self._start_time
        now_wall = datetime.now(timezone.utc)

        data: dict = {
            "pid": os.getpid(),
            "status": status,
            "started_at": self._start_wall.strftime(_ISO_FMT),
            "updated_at": now_wall.strftime(_ISO_FMT),
            "completed_rows": completed,
            "error_rows": errors,
            "total_rows": self._total_rows,
            "elapsed_seconds": round(elapsed, 1),
        }

        if concurrency is not None:
            data["current_concurrency"] = concurrency

        if self._total_rows and completed > 0:
            data["progress_pct"] = round(completed / self._total_rows * 100, 1)

        if elapsed > 0 and completed > 0:
            data["rows_per_minute"] = round(completed / elapsed * 60, 1)

        # アトミック書き込み: 一時ファイル → os.replace()
        dir_name = os.path.dirname(self._path) or "."
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".hb.tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._path)
            except BaseException:
                # 一時ファイルのクリーンアップ
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError:
            # ディスクフル等で書き込めなくてもプロセスは続行する
            pass


__all__ = ["ShutdownManager", "HeartbeatWriter"]
