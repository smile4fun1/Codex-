from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.memory import MemoryManager, TaskRecord
from wrapper.notifications import TelegramNotifier


def load_config(root: Path) -> dict[str, object]:
    config_path = root / "config.toml"
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def get_notifier(root: Path) -> TelegramNotifier:
    config = load_config(root)
    if config.get("telegram_token") and config.get("chat_id"):
        return TelegramNotifier(str(config.get("telegram_token", "")), str(config.get("chat_id", "")))
    telegram = config.get("telegram") or config.get("wrapper", {}).get("telegram", {})
    if not isinstance(telegram, dict):
        telegram = {}
    return TelegramNotifier(str(telegram.get("telegram_token", "")), str(telegram.get("chat_id", "")))


def _now() -> datetime:
    return datetime.now().astimezone()


def task_is_due(task: dict[str, object], now: datetime) -> bool:
    if not task.get("enabled", True):
        return False
    schedule = str(task.get("schedule", ""))
    last_run = str(task.get("last_run") or "").strip()
    if schedule.startswith("interval:"):
        seconds = int(schedule.split(":", 1)[1])
        if not last_run:
            return True
        previous = datetime.fromisoformat(last_run)
        return (now - previous).total_seconds() >= seconds
    if schedule.startswith("daily:"):
        hour, minute = schedule.split(":", 1)[1].split(":")
        target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        if now < target:
            return False
        if not last_run:
            return True
        previous = datetime.fromisoformat(last_run)
        return previous.date() < now.date()
    return False


def execute_task(root: Path, task: dict[str, object], notifier: TelegramNotifier) -> dict[str, object]:
    from main import build_codex_command, resolve_codex_runtime

    prompt = str(task.get("prompt", "")).strip()
    command = resolve_codex_runtime()
    command.extend(["-c", "personality=pragmatic", "exec", "--skip-git-repo-check", prompt])
    env = os.environ.copy()
    env["CODEX_HOME"] = str(root)
    env["HOME"] = str(root)
    env["CODEX_WRAPPER_LOOP_ACTIVE"] = "1"
    proc = subprocess.run(command, cwd=str(root), capture_output=True, text=True, env=env, check=False)
    output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    record = TaskRecord(
        timestamp=_now().isoformat(timespec="seconds"),
        prompt=prompt,
        plan=[f"Scheduled task `{task.get('id', 'unknown')}` executed via wrapper loop."],
        outcome=output[:5000],
        success=proc.returncode == 0,
        skills=[],
        tags=[str(task.get("type", "")), "scheduled", str(task.get("id", ""))],
        summary=MemoryManager.summarize(prompt, output, [str(task.get("type", "")), "scheduled"]),
    )
    manager = MemoryManager(root)
    manager.save_task_result(record, source=f"task:{task.get('id', 'unknown')}")
    if notifier.enabled:
        notifier.send(f"[{task.get('id', 'task')}] {record.summary}")
    return {"ok": proc.returncode == 0, "output": output, "returncode": proc.returncode}


def run_once(root: Path) -> int:
    manager = MemoryManager(root)
    payload = manager.load_tasks()
    tasks = payload.get("tasks", [])
    notifier = get_notifier(root)
    now = _now()
    changed = False
    for task in tasks:
        if not task_is_due(task, now):
            continue
        result = execute_task(root, task, notifier)
        task["last_run"] = now.isoformat(timespec="seconds")
        task["last_result"] = {"ok": result["ok"], "returncode": result["returncode"]}
        changed = True
    if changed:
        manager.save_tasks(tasks)
    return 0


def loop_state_path(root: Path) -> Path:
    return root / "wrapper-memory" / "loop_state.json"


def write_loop_state(root: Path) -> None:
    path = loop_state_path(root)
    payload = {"pid": os.getpid(), "last_heartbeat": _now().isoformat(timespec="seconds")}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_forever(root: Path, interval: int) -> int:
    while True:
        write_loop_state(root)
        run_once(root)
        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.once:
        return run_once(ROOT)
    return run_forever(ROOT, args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
