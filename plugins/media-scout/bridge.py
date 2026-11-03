"""Narrow adapter to the public Hermes Kanban CLI through the terminal tool."""
from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
from pathlib import Path
from typing import Callable

_SLUG = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ORIGIN_FIELDS = ("platform", "chat_id", "thread_id", "message_id", "user_id", "guild_id", "parent_chat_id", "session_key", "chat_type")
_MAX_BODY = 48_000


class BridgeError(RuntimeError):
    def __init__(self, message: str, task_id: str = ""):
        super().__init__(message)
        self.task_id = task_id


class NativeBridge:
    def __init__(self, ctx, home: Path, board: str, assignee: str):
        if os.name != "posix":
            raise RuntimeError("media-scout native bridge supports Linux/POSIX hosts only")
        if not isinstance(board, str) or not _SLUG.fullmatch(board):
            raise ValueError("invalid Kanban board slug")
        if not isinstance(assignee, str) or not _SLUG.fullmatch(assignee):
            raise ValueError("invalid review profile slug")
        launcher = shutil.which("hermes")
        if not launcher or not Path(launcher).is_absolute():
            raise ValueError("native Hermes launcher must be discoverable in the host PATH")
        self.cli = launcher
        self.ctx = ctx
        self.home = Path(home).expanduser().absolute()
        self.board = board
        self.assignee = assignee

    def _base(self) -> str:
        # --board is authoritative. Clear inherited redirects that otherwise take precedence.
        return (f"env -u HERMES_KANBAN_DB -u HERMES_KANBAN_BOARD "
                f"HERMES_HOME={shlex.quote(str(self.home))} {shlex.quote(self.cli)} kanban "
                f"--board {shlex.quote(self.board)}")

    def _dispatch(self, command: str) -> str:
        try:
            raw = self.ctx.dispatch_tool("terminal", {"command": command, "timeout": 30})
        except Exception as exc:
            raise BridgeError("native terminal dispatch failed") from exc
        if not isinstance(raw, str) or len(raw) > 1_000_000:
            raise BridgeError("native terminal returned malformed or oversized output")
        try:
            envelope = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise BridgeError("native terminal response was not JSON") from exc
        if not isinstance(envelope, dict):
            raise BridgeError("native terminal response must be an object")
        if envelope.get("error") is not None or envelope.get("exit_code") != 0:
            diagnostic = str(envelope.get("error") or envelope.get("output") or "no diagnostic")[-800:]
            raise BridgeError(f"native Kanban command failed or was denied (exit {envelope.get('exit_code')}): {diagnostic}")
        output = envelope.get("output")
        if not isinstance(output, str):
            raise BridgeError("native terminal output field was malformed")
        return output

    def _json_command(self, command: str):
        # Native task bodies/runs can exceed terminal stdout truncation limits.
        path = self._packet_root() / f"response-{secrets.token_hex(16)}.json"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            self._dispatch(f"{command} > {shlex.quote(str(path))}")
            if path.is_symlink() or path.stat().st_size > 1_000_000:
                raise BridgeError("native JSON response is unsafe or exceeds bounded size")
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise BridgeError("native Kanban JSON output was malformed") from exc
        finally:
            path.unlink(missing_ok=True)

    def _profile(self) -> str:
        if self.home.parent.name == "profiles" and _SLUG.fullmatch(self.home.name):
            return self.home.name
        return "default"

    def _packet_root(self) -> Path:
        home = self.home
        if home.is_symlink():
            raise BridgeError("unsafe Hermes home symlink")
        root = home / "plugin-data" / "media-scout" / "packets"
        current = home
        for part in ("plugin-data", "media-scout", "packets"):
            current = current / part
            if current.is_symlink():
                raise BridgeError("plugin packet path contains a symlink")
            current.mkdir(exist_ok=True)
            if not current.is_dir():
                raise BridgeError("plugin packet path is not a directory")
        resolved = root.resolve(strict=True)
        if not resolved.is_relative_to(home.resolve(strict=True)):
            raise BridgeError("plugin packet path escaped Hermes home")
        return resolved

    def _write_packet(self, body: str) -> Path:
        if not isinstance(body, str) or not body.strip() or len(body.encode("utf-8")) > _MAX_BODY:
            raise BridgeError("review packet must be nonempty and bounded")
        root = self._packet_root()
        path = root / f"review-{secrets.token_hex(16)}.md"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            path.unlink(missing_ok=True)
            raise BridgeError("unsafe review packet path")
        return path

    @staticmethod
    def _validate_origin(origin: dict) -> dict:
        if not isinstance(origin, dict) or set(origin) != set(_ORIGIN_FIELDS):
            raise BridgeError("review origin must contain the exact immutable source fields")
        clean = {}
        for name in _ORIGIN_FIELDS:
            value = origin[name]
            if name == "thread_id" and value is None:
                value = ""
            if name == "parent_chat_id" and value is None:
                value = ""
            if name == "guild_id" and value is None:
                value = ""
            if not isinstance(value, str) or len(value) > 256 or (value and not _TOKEN.fullmatch(value)):
                raise BridgeError(f"invalid source field: {name}")
            if name not in {"thread_id", "parent_chat_id", "guild_id"} and not value:
                raise BridgeError(f"missing source field: {name}")
            clean[name] = value
        if clean["platform"] != "discord":
            raise BridgeError("only Discord review origins are supported")
        return clean

    @staticmethod
    def _task(value, task_id: str = "") -> dict:
        if not isinstance(value, dict):
            raise BridgeError("native task JSON was not an object", task_id)
        task = value.get("task", value)
        if not isinstance(task, dict):
            raise BridgeError("native task wrapper was malformed", task_id)
        actual_id = task.get("id") or task.get("task_id") or task_id
        if not isinstance(actual_id, str) or not _TOKEN.fullmatch(actual_id):
            raise BridgeError("native task response omitted a valid task ID", task_id)
        return task

    @staticmethod
    def _marker(origin: dict) -> str:
        return "<!-- media-scout-origin:" + json.dumps(origin, sort_keys=True, separators=(",", ":")) + " -->"

    @classmethod
    def packet_body(cls, body: str, origin: dict, key: str) -> str:
        return body.rstrip() + "\n\n<!-- media-scout-review-key:" + key + " -->\n" + cls._marker(origin)

    @staticmethod
    def _initial_hold(task: dict) -> bool:
        # Native CLI omits block_kind. Use actual event/run history, never absence of a field.
        events, runs, comments = task.get("events"), task.get("runs"), task.get("comments")
        return (task.get("block_kind") is None and isinstance(events, list) and len(events) == 2
                and events[0].get("kind") == "created" and events[0].get("payload", {}).get("status") == "blocked"
                and events[1].get("kind") == "blocked" and events[1].get("payload", {}).get("reason") == "initial_status"
                and runs == [] and comments == [])

    def _show(self, task_id: str) -> dict:
        result = self._json_command(f"{self._base()} show {shlex.quote(task_id)} --json")
        task = dict(self._task(result, task_id))
        for field in ("events", "runs", "comments", "latest_summary"):
            task[field] = result.get(field)
        return task

    def _verify_task(self, task: dict, key: str, assignee: str, body: str, task_id: str) -> dict:
        if ("idempotency_key" in task and task["idempotency_key"] != key) or task.get("assignee") != assignee or task.get("body") != body:
            raise BridgeError("existing task conflicts with this review key, assignee, or source packet", task_id)
        if task.get("status") not in {"triage", "todo", "blocked", "ready", "running", "review", "done", "archived", "failed", "cancelled"}:
            raise BridgeError("native task has an unknown state", task_id)
        return task

    def _subscriptions(self, task_id: str):
        result = self._json_command(f"{self._base()} notify-list {shlex.quote(task_id)} --json")
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise BridgeError("native notify-list returned malformed JSON", task_id)
        return result

    @staticmethod
    def _matches_subscription(sub: dict, task_id: str, origin: dict, profile: str) -> bool:
        metadata = sub.get("delivery_metadata") if isinstance(sub.get("delivery_metadata"), dict) else {}
        return (sub.get("task_id") == task_id and sub.get("platform") == "discord"
                and sub.get("chat_id") == origin["chat_id"] and (sub.get("thread_id") or "") == origin["thread_id"]
                and sub.get("user_id") == origin["user_id"] and sub.get("notifier_profile") == profile
                and sub.get("delivery_mode") == "notify+wake" and sub.get("chat_type") == origin["chat_type"]
                and (metadata.get("parent_chat_id") or "") == origin["parent_chat_id"]
                and (metadata.get("guild_id") or "") == origin["guild_id"])

    def ensure_review(self, key: str, origin: dict, body: str, task_id: str = "", allow_release: Callable[[], bool] | None = None) -> dict:
        committed_id = task_id if isinstance(task_id, str) else ""
        packet = None
        try:
            if not isinstance(key, str) or not _TOKEN.fullmatch(key):
                raise BridgeError("invalid review idempotency key")
            source = self._validate_origin(origin)
            marker = self._marker(source)
            marked_body = self.packet_body(body, source, key)
            packet = self._write_packet(marked_body)
            if task_id:
                task = self._show(task_id)
                committed_id = task_id
                self._verify_task(task, key, self.assignee, marked_body, task_id)
            else:
                create = (f"{self._base()} create 'Media Scout review' --body-file {shlex.quote(str(packet))} "
                          f"--assignee {shlex.quote(self.assignee)} --idempotency-key {shlex.quote(key)} "
                          "--initial-status blocked --max-runtime 10m --max-retries 1 --completion-contract local-only --json")
                task = self._task(self._json_command(create))
                committed_id = task.get("id") or task.get("task_id") or ""
                if not isinstance(committed_id, str) or not _TOKEN.fullmatch(committed_id):
                    raise BridgeError("create output omitted a valid task ID")
                self._verify_task(task, key, self.assignee, marked_body, committed_id)

            profile = self._profile()
            subs = self._subscriptions(committed_id)
            matching = [s for s in subs if self._matches_subscription(s, committed_id, source, profile)]
            if subs and not matching:
                raise BridgeError("task already has a conflicting native source subscription", committed_id)
            if not matching:
                subscribe = (
                    f"{self._base()} notify-subscribe {shlex.quote(committed_id)} "
                    f"--platform discord --chat-id {shlex.quote(source['chat_id'])} "
                    + (f"--thread-id {shlex.quote(source['thread_id'])} " if source["thread_id"] else "")
                    + f"--user-id {shlex.quote(source['user_id'])} "
                    + f"--chat-type {shlex.quote(source['chat_type'])} "
                    + (f"--parent-chat-id {shlex.quote(source['parent_chat_id'])} " if source["parent_chat_id"] else "")
                    + (f"--guild-id {shlex.quote(source['guild_id'])} " if source["guild_id"] else "")
                    + f"--notifier-profile {shlex.quote(profile)} --delivery-mode 'notify+wake'"
                )
                self._dispatch(subscribe)
                subs = self._subscriptions(committed_id)
                matching = [s for s in subs if self._matches_subscription(s, committed_id, source, profile)]
                if len(matching) != 1:
                    raise BridgeError("native source subscription could not be verified", committed_id)

            task = self._verify_task(self._show(committed_id), key, self.assignee, marked_body, committed_id)
            status = task["status"]
            if status == "blocked" and self._initial_hold(task):
                if allow_release is None or not allow_release():
                    return {"task_id": committed_id, "status": "blocked", "source_verified": True, "released": False, "task": task, "source_fields_verified": ["platform", "chat_id", "thread_id", "user_id", "guild_id", "parent_chat_id", "notifier_profile", "delivery_mode", "message_id:task_marker", "session_key:task_marker"]}
                self._dispatch(f"{self._base()} unblock {shlex.quote(committed_id)} --reason 'media-scout initial safety hold'")
                task = self._verify_task(self._show(committed_id), key, self.assignee, marked_body, committed_id)
                if task.get("status") not in {"todo", "ready", "running", "review", "done", "archived", "failed", "cancelled"}:
                    raise BridgeError("task release did not reach a recognized state", committed_id)
                status = task["status"]
            return {"task_id": committed_id, "status": status, "source_verified": True, "released": status != "blocked", "task": task, "source_fields_verified": ["platform", "chat_id", "thread_id", "user_id", "guild_id", "parent_chat_id", "notifier_profile", "delivery_mode", "message_id:task_marker", "session_key:task_marker"]}
        except BridgeError as exc:
            return {"error": str(exc), **({"task_id": exc.task_id or committed_id} if exc.task_id or committed_id else {})}
        except Exception:
            return {"error": "native review bridge failed", **({"task_id": committed_id} if committed_id else {})}
        finally:
            if packet is not None:
                try:
                    packet.unlink(missing_ok=True)
                except OSError:
                    pass

    def status(self, task_id: str) -> dict:
        try:
            if not isinstance(task_id, str) or not _TOKEN.fullmatch(task_id):
                return {"error": "invalid task ID"}
            task = self._show(task_id)
            status = task.get("status")
            if status not in {"triage", "todo", "blocked", "ready", "running", "review", "done", "archived", "failed", "cancelled"}:
                return {"error": "native task state was missing or unknown", "task_id": task_id}
            return {"task_id": task_id, "status": status, "task": task}
        except BridgeError as exc:
            return {"error": str(exc), **({"task_id": exc.task_id or task_id} if exc.task_id or task_id else {})}
