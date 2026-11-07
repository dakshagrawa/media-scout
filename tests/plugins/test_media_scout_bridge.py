import importlib.util
import json
import shlex
import shutil
import pytest
from pathlib import Path

ROOT = Path(__file__).parents[2]
BRIDGE = ROOT / "plugins" / "media-scout" / "bridge.py"
ORIGIN = {
    "platform": "discord", "chat_type": "group", "chat_id": "chat-7", "thread_id": "thread-9",
    "message_id": "msg-1", "user_id": "user-2", "guild_id": "guild-3",
    "parent_chat_id": "parent-8", "session_key": "discord:chat-7:thread-9",
}
KEY = "media-scout:abcdef123456"
BODY = "review packet: ordinary text with `$(touch /tmp/nope)`"


@pytest.fixture(autouse=True)
def native_launcher(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/fixture/bin/hermes")



def load():
    spec = importlib.util.spec_from_file_location("media_scout_bridge", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def redirect_output(handler):
    def dispatch(self, name, args, **kwargs):
        result = handler(self, name, args, **kwargs)
        argv = shlex.split(args["command"])
        if len(argv) >= 2 and argv[-2] == ">":
            envelope = json.loads(result)
            if envelope.get("exit_code") == 0 and envelope.get("output"):
                Path(argv[-1]).write_text(envelope["output"])
                envelope["output"] = ""
            return json.dumps(envelope)
        return result
    return dispatch


class Fake:
    def __init__(self):
        self.calls = []
        self.task = None
        self.subscriptions = []

    @redirect_output
    def dispatch_tool(self, name, args, **kwargs):
        assert name == "terminal"
        self.calls.append((args, kwargs))
        command = args["command"]
        if " create " in command:
            assert "$(touch /tmp/nope)" not in command
            argv = shlex.split(command)
            packet = Path(argv[argv.index("--body-file") + 1]).read_text()
            self.task = {"id": "t_12345678", "title": "Media Scout review", "body": packet, "status": "blocked", "assignee": "reviewer", "idempotency_key": KEY, "block_kind": None}
            return json.dumps({"output": json.dumps(self.task), "exit_code": 0, "error": None})
        if " notify-subscribe " in command:
            self.subscriptions = [{"task_id": "t_12345678", "platform": "discord", "chat_type": "group", "chat_id": "chat-7", "thread_id": "thread-9", "user_id": "user-2", "notifier_profile": "default", "delivery_mode": "notify+wake", "chat_type": "group", "delivery_metadata": {"parent_chat_id": "parent-8", "guild_id": "guild-3"}}]
            return json.dumps({"output": "Subscribed", "exit_code": 0, "error": None})
        if " notify-list " in command:
            return json.dumps({"output": json.dumps(self.subscriptions), "exit_code": 0, "error": None})
        if " show " in command:
            return json.dumps({"output": json.dumps({"task": self.task, "latest_summary": self.task.get("latest_summary"), "events": self.task.get("events", [{"kind": "created", "payload": {"status": "blocked"}}, {"kind": "blocked", "payload": {"reason": "initial_status"}}]), "runs": self.task.get("runs", []), "comments": []}), "exit_code": 0, "error": None})
        if " unblock " in command:
            self.task["status"] = "ready"
            return json.dumps({"output": "Unblocked t_12345678", "exit_code": 0, "error": None})
        raise AssertionError(command)


def test_native_review_protocol_is_create_verify_then_unblock(tmp_path):
    mod = load()
    ctx = Fake()
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    result = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: True)
    assert result["task_id"] == "t_12345678" and result["status"] == "ready"
    commands = [call[0]["command"] for call in ctx.calls]
    verbs = [shlex.split(c)[shlex.split(c).index("kanban") + 3] for c in commands]
    assert verbs == ["create", "notify-list", "notify-subscribe", "notify-list", "notify-list", "show", "unblock", "show"]
    assert "--initial-status blocked" in commands[0]
    assert "notify+wake" in commands[2]
    assert all("HERMES_HOME=" in c and "-u HERMES_KANBAN_DB" in c and "-u HERMES_KANBAN_BOARD" in c for c in commands)
    assert all("HERMES_HOME=" in c and "HERMES_KANBAN_DB" in c for c in commands)


def test_replay_does_not_retarget_or_reopen_ready_task(tmp_path):
    mod = load()
    ctx = Fake()
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    first = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: True)
    ctx.calls.clear()
    second = bridge.ensure_review(KEY, ORIGIN, BODY, task_id=first["task_id"], allow_release=lambda: True)
    assert second["task_id"] == first["task_id"] and second["status"] == "ready"
    assert not any(" create " in c[0]["command"] or " unblock " in c[0]["command"] for c in ctx.calls)


def test_failure_before_verification_never_releases_and_surfaces_committed_id(tmp_path):
    mod = load()
    ctx = Fake()
    def dispatch(name, args, **kwargs):
        ctx.calls.append((args, kwargs))
        cmd = args["command"]
        if " create " in cmd:
            argv = shlex.split(cmd)
            packet = Path(argv[argv.index("--body-file") + 1]).read_text()
            ctx.task = {"id": "t_12345678", "body": packet, "status": "blocked", "assignee": "reviewer", "idempotency_key": KEY, "block_kind": None}
            return json.dumps({"output": json.dumps(ctx.task), "exit_code": 0, "error": None})
        if " notify-subscribe " in cmd:
            return json.dumps({"output": "Subscribed", "exit_code": 0, "error": None})
        if " notify-list " in cmd:
            return json.dumps({"output": "[]", "exit_code": 0, "error": None})
        raise AssertionError("unexpected command")
    ctx.dispatch_tool = redirect_output(lambda self, name, args, **kw: dispatch(name, args, **kw)).__get__(ctx)
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    result = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: True)
    assert result["error"] and result["task_id"] == "t_12345678"
    assert not any(" unblock " in c[0]["command"] for c in ctx.calls)


def test_release_is_deferred_without_fresh_authorization(tmp_path):
    mod = load()
    ctx = Fake()
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    result = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: False)
    assert result["status"] == "blocked" and result["released"] is False
    assert not any(" unblock " in c[0]["command"] for c in ctx.calls)


def test_rejects_invalid_slugs_and_origin_command_injection(tmp_path):
    mod = load()
    ctx = Fake()
    for board, assignee in (("../x", "reviewer"), ("good", "$(id)")):
        try:
            mod.NativeBridge(ctx, tmp_path, board, assignee)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe slug accepted")
    origin = dict(ORIGIN, chat_id="x; touch /tmp/pwn")
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    result = bridge.ensure_review(KEY, origin, BODY)
    assert result["error"] and not ctx.calls


def test_existing_noninitial_block_is_never_unblocked(tmp_path):
    mod = load()
    ctx = Fake()
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: True)
    ctx.task["status"] = "blocked"
    ctx.task["block_kind"] = "manual"
    ctx.calls.clear()
    result = bridge.ensure_review(KEY, ORIGIN, BODY, task_id="t_12345678", allow_release=lambda: True)
    assert result["status"] == "blocked" and result["released"] is False
    assert not any(" unblock " in call[0]["command"] for call in ctx.calls)


def test_conflicting_subscription_fails_closed_without_retarget(tmp_path):
    mod = load()
    ctx = Fake()
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: False)
    ctx.calls.clear()
    ctx.subscriptions[0]["chat_id"] = "different-chat"
    result = bridge.ensure_review(KEY, ORIGIN, BODY, task_id="t_12345678", allow_release=lambda: True)
    assert result["error"] and result["task_id"] == "t_12345678"
    assert not any("notify-subscribe" in call[0]["command"] or " unblock " in call[0]["command"] for call in ctx.calls)


def test_duplicate_matching_subscription_never_releases(tmp_path):
    mod = load(); ctx = Fake()
    bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    first = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=False)
    ctx.subscriptions.append(dict(ctx.subscriptions[0]))
    ctx.calls.clear()
    result = bridge.ensure_review(KEY, ORIGIN, BODY, task_id=first["task_id"], allow_release=lambda: True)
    assert result.get("error") and result["task_id"] == first["task_id"]
    assert not any(" unblock " in call[0]["command"] for call in ctx.calls)


def test_malformed_terminal_json_is_not_success(tmp_path):
    mod = load()
    class Broken:
        def dispatch_tool(self, *args, **kwargs):
            return '{"output":"{bad","exit_code":0,"error":null}'
    bridge = mod.NativeBridge(Broken(), tmp_path, "media-review", "reviewer")
    result = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: True)
    assert result["error"] and "task_id" not in result


def test_status_reads_current_native_task_json(tmp_path):
    mod = load()
    ctx = Fake()
    ctx.task = {"id": "t_12345678", "status": "done", "assignee": "reviewer", "body": BODY, "idempotency_key": KEY}
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").status("t_12345678", ORIGIN)
    assert result["task_id"] == "t_12345678" and result["status"] == "done"
    assert result["review_verification"] == "unverified"
    assert len(ctx.calls) == 2 and "show t_12345678 --json" in ctx.calls[0][0]["command"]


def test_status_requires_observed_successful_assigned_run_and_matching_handoff(tmp_path):
    mod = load(); ctx = Fake()
    ctx.task = {"id": "t_12345678", "status": "done", "assignee": "reviewer", "body": BODY, "idempotency_key": KEY}
    run = {"id": 41, "profile": "reviewer", "status": "done", "outcome": "completed", "summary": "Reviewed source evidence.", "started_at": 100, "ended_at": 123}
    ctx.task.update(runs=[run], latest_summary=run["summary"], events=[{"kind": "completed", "run_id": 41}])
    ctx.subscriptions = [{"task_id": "t_12345678", "platform": "discord", "chat_type": "group", "chat_id": "chat-7", "thread_id": "thread-9", "user_id": "user-2", "notifier_profile": "default", "delivery_mode": "notify+wake", "delivery_metadata": {"parent_chat_id": "parent-8", "guild_id": "guild-3"}}]
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").status("t_12345678", ORIGIN)
    assert result["review_verification"] == "verified"
    assert result["task"]["latest_summary"] == "Reviewed source evidence."


@pytest.mark.parametrize("change", ["missing_completion_event", "mismatched_completion_event", "latest_summary_mismatch"])
def test_completion_proof_must_match_qualifying_run(tmp_path, change):
    mod = load(); ctx = Fake()
    run = {"id": 41, "profile": "reviewer", "status": "done", "outcome": "completed", "summary": "Reviewed source evidence.", "started_at": 100, "ended_at": 123}
    events = [{"kind": "completed", "run_id": 41}]
    latest = run["summary"]
    if change == "missing_completion_event": events = []
    if change == "mismatched_completion_event": events = [{"kind": "completed", "run_id": 42}]
    if change == "latest_summary_mismatch": latest = "Another run's summary."
    ctx.task = {"id": "t_12345678", "status": "done", "assignee": "reviewer", "body": BODY, "runs": [run], "events": events, "latest_summary": latest}
    ctx.subscriptions = [{"task_id": "t_12345678", "platform": "discord", "chat_type": "group", "chat_id": "chat-7", "thread_id": "thread-9", "user_id": "user-2", "notifier_profile": "default", "delivery_mode": "notify+wake", "delivery_metadata": {"parent_chat_id": "parent-8", "guild_id": "guild-3"}}]
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").status("t_12345678", ORIGIN)
    assert result["review_verification"] == "unverified"


@pytest.mark.parametrize("extra", [
    {"id": 42, "profile": "operator", "status": "done", "outcome": "completed", "summary": "operator", "ended_at": 124},
    {"id": 42, "profile": "reviewer", "status": "done", "outcome": "completed", "summary": "", "ended_at": 124},
    {"id": 42, "profile": "reviewer", "status": "done", "outcome": "completed", "summary": "operator completion", "started_at": 124, "ended_at": 124},
])
def test_foreign_or_malformed_run_never_verifies(tmp_path, extra):
    mod = load(); ctx = Fake()
    ctx.task = {"id": "t_12345678", "status": "done", "assignee": "reviewer", "body": BODY, "runs": [extra], "events": [{"kind": "completed", "run_id": extra["id"]}], "latest_summary": extra["summary"]}
    ctx.subscriptions = [{"task_id": "t_12345678", "platform": "discord", "chat_type": "group", "chat_id": "chat-7", "thread_id": "thread-9", "user_id": "user-2", "notifier_profile": "default", "delivery_mode": "notify+wake", "delivery_metadata": {"parent_chat_id": "parent-8", "guild_id": "guild-3"}}]
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").status("t_12345678", ORIGIN)
    assert result["review_verification"] == "unverified"


@pytest.mark.parametrize("subs", [
    [],
    [{"task_id": "t_12345678", "platform": "discord", "chat_id": "chat-7", "thread_id": "thread-9", "user_id": "user-2", "notifier_profile": "default", "delivery_mode": "notify+wake", "chat_type": "group", "delivery_metadata": {"parent_chat_id": "parent-8", "guild_id": "guild-3"}}, {"task_id": "t_12345678", "platform": "discord", "chat_id": "other", "delivery_mode": "notify+wake"}],
])
def test_subscription_mismatch_or_duplicates_do_not_verify(tmp_path, subs):
    mod = load(); ctx = Fake(); ctx.task = {"id": "t_12345678", "status": "done"}; ctx.subscriptions = subs
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").status("t_12345678", ORIGIN)
    assert result.get("review_verification") == "unverified" or result.get("error")


def test_packet_root_symlink_is_rejected_before_dispatch(tmp_path):
    mod = load()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "plugin-data").symlink_to(outside, target_is_directory=True)
    ctx = Fake()
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").ensure_review(KEY, ORIGIN, BODY)
    assert result["error"] and not ctx.calls


def test_host_resolved_cli_survives_terminal_path_reset(monkeypatch, tmp_path):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: "/opt/hermes-agent/bin/hermes")
    mod = load()
    assert "/opt/hermes-agent/bin/hermes kanban" in mod.NativeBridge(Fake(), tmp_path, "media-review", "reviewer")._base()


def test_native_task_json_without_idempotency_field_is_verified_by_exact_marked_body(tmp_path):
    mod = load(); ctx = Fake(); base = ctx.dispatch_tool
    def dispatch(name, args, **kw):
        result = json.loads(base(name, args, **kw))
        out = Path(shlex.split(args["command"])[-1])
        payload = json.loads(out.read_text()) if shlex.split(args["command"])[-2] == ">" else None
        if " create " in args["command"] and payload:
            payload.pop("idempotency_key", None); out.write_text(json.dumps(payload))
        return json.dumps(result)
    ctx.dispatch_tool = redirect_output(lambda self, name, args, **kw: dispatch(name, args, **kw)).__get__(ctx)
    result = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer").ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: True)
    assert result["status"] == "ready", result


def test_native_blocked_event_without_block_kind_is_never_auto_released(tmp_path):
    mod = load(); ctx = Fake(); bridge = mod.NativeBridge(ctx, tmp_path, "media-review", "reviewer")
    first = bridge.ensure_review(KEY, ORIGIN, BODY, allow_release=lambda: False)
    base = ctx.dispatch_tool
    def dispatch(name, args, **kw):
        result = json.loads(base(name, args, **kw))
        if " show " in args["command"]:
            out = Path(shlex.split(args["command"])[-1])
            payload = json.loads(out.read_text())
            payload["task"].pop("block_kind", None)
            payload["events"].append({"kind": "blocked", "payload": {"reason": "owner deferred"}})
            out.write_text(json.dumps(payload))
        return json.dumps(result)
    ctx.dispatch_tool = redirect_output(lambda self, name, args, **kw: dispatch(name, args, **kw)).__get__(ctx); ctx.calls.clear()
    result = bridge.ensure_review(KEY, ORIGIN, BODY, task_id=first["task_id"], allow_release=lambda: True)
    assert result["status"] == "blocked"
    assert not any(" unblock " in c[0]["command"] for c in ctx.calls)


def test_native_json_uses_owned_file_not_truncatable_terminal_stdout(tmp_path):
    mod = load()
    class Output:
        def dispatch_tool(self, name, args):
            argv = shlex.split(args["command"])
            assert argv[-2] == ">"
            Path(argv[-1]).write_text(json.dumps({"large": "x" * 100000}))
            return json.dumps({"output": "", "exit_code": 0, "error": None})
    bridge = mod.NativeBridge(Output(), tmp_path, "media-review", "reviewer")
    assert len(bridge._json_command("hermes safe-fixture")["large"]) == 100000
    assert not list((tmp_path / "plugin-data/media-scout/packets").glob("response-*"))
