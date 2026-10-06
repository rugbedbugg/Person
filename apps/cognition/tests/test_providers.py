"""Sterile provider backends, offline (ADR 0020, C2).

No provider is called here: the sandboxed process is replaced by canned
outputs, except for the model-free sandbox self-check, which runs for real
where bubblewrap can.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
from person_cognition.deliberation import SterilityFailure
from person_cognition.deliberation import sterile as sterile_module
from person_cognition.deliberation.providers import (
    CODEX_DISABLED_FEATURES,
    BudgetExhausted,
    CallBudget,
    ClaudeCodeModel,
    CodexModel,
)
from person_cognition.deliberation.sterile import Credential, Sandbox, SterilityError, self_check


@pytest.fixture
def credential(tmp_path: Path) -> Path:
    path = tmp_path / "credentials.json"
    path.write_text("{}", encoding="utf-8")
    return path


class Canned:
    """What the sandboxed CLI prints, per call, and what it was asked."""

    def __init__(self, *outputs: tuple[int, str, str] | type[BaseException]) -> None:
        self.outputs = list(outputs)
        self.argv: list[list[str]] = []
        self.stdin: list[str] = []

    def __call__(
        self, sandbox: Sandbox, argv: list[str], *, stdin: str, timeout_s: float
    ) -> subprocess.CompletedProcess[str]:
        self.argv.append(list(argv))
        self.stdin.append(stdin)
        output = self.outputs.pop(0)
        if isinstance(output, type):
            raise subprocess.TimeoutExpired(argv, timeout_s)
        code, stdout, stderr = output
        return subprocess.CompletedProcess(argv, code, stdout, stderr)


def lines(*events: dict[str, Any]) -> str:
    return "\n".join(json.dumps(event) for event in events)


ANSWER = {"assessment": {"summary": "ok", "premises": ["s1"]}}


def claude(tmp_path: Path, credential: Path, budget: int = 5) -> ClaudeCodeModel:
    return ClaudeCodeModel(
        model="claude-test",
        budget=CallBudget(budget),
        quarantine=tmp_path / "quarantine",
        credentials=credential,
    )


def codex(tmp_path: Path, credential: Path, budget: int = 5) -> CodexModel:
    return CodexModel(
        model="codex-test",
        budget=CallBudget(budget),
        quarantine=tmp_path / "quarantine",
        credentials=credential,
    )


CLAUDE_OK = lines(
    {"type": "system", "subtype": "init", "tools": [], "mcp_servers": [], "cwd": "/sandbox/work"},
    {
        "type": "result",
        "is_error": False,
        "structured_output": ANSWER,
        "usage": {"input_tokens": 9},
    },
)


def use(monkeypatch: pytest.MonkeyPatch, canned: Canned) -> Canned:
    def run(
        self: Sandbox, argv: list[str], *, stdin: str, timeout_s: float
    ) -> subprocess.CompletedProcess[str]:
        return canned(self, argv, stdin=stdin, timeout_s=timeout_s)

    monkeypatch.setattr(Sandbox, "run", run)
    # The canned process never runs, so a host without bubblewrap (CI) can
    # still test the adapters. Production fails closed without it.
    monkeypatch.setattr(sterile_module, "bubblewrap", lambda: "/nonexistent/bwrap")
    return canned


# ------------------------------------------------------------ Claude Code


def test_claude_is_invoked_with_every_capability_off_and_answers(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canned = use(monkeypatch, Canned((0, CLAUDE_OK, "")))
    backend = claude(tmp_path, credential)
    response = backend.deliberate("INSTRUCTION", "CONTEXT", timeout_s=10)
    argv = canned.argv[0]
    for flag in (
        "-p",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
    ):
        assert flag in argv, flag
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1] == "INSTRUCTION"
    assert "--bare" not in argv, "subscription auth needs OAuth"
    assert canned.stdin == ["CONTEXT"], "the context goes on stdin, alone"
    assert response.status == "answered" and json.loads(response.text) == ANSWER
    assert "sterile-v1" in response.backend_version
    assert backend.budget.completed == 1 and backend.budget.input_tokens == 9


@pytest.mark.parametrize(
    "event",
    [
        {"type": "system", "subtype": "init", "tools": ["Bash", "Read"], "mcp_servers": []},
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": [{"name": "x"}]},
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": [], "cwd": "/home/u"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
    ],
)
def test_a_claude_capability_where_none_may_exist_disables_the_backend(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch, event: dict[str, Any]
) -> None:
    canned = use(monkeypatch, Canned((0, lines(event), "")))
    backend = claude(tmp_path, credential)
    with pytest.raises(SterilityFailure) as raised:
        backend.deliberate("I", "C", timeout_s=10)
    assert backend.disabled is not None
    (quarantined,) = (tmp_path / "quarantine").iterdir()
    assert stat.S_IMODE(quarantined.stat().st_mode) == 0o600
    assert raised.value.output_sha256 and quarantined.name.startswith("sterility-failure-")
    with pytest.raises(SterilityFailure):
        backend.deliberate("I", "C", timeout_s=10)
    assert len(canned.argv) == 1 and backend.budget.attempted == 1, "nothing spawned once disabled"


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        (
            (1, lines({"type": "result", "is_error": True, "result": "Usage limit reached"}), ""),
            "quota",
        ),
        ((1, "", "Error: not logged in. Please run /login"), "authentication"),
        ((1, "", "segfault"), "backend"),
        (subprocess.TimeoutExpired, "timeout"),
    ],
)
def test_claude_with_no_answer_is_typed_unavailability(
    tmp_path: Path,
    credential: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Any,
    reason: str,
) -> None:
    use(monkeypatch, Canned(output))
    response = claude(tmp_path, credential).deliberate("I", "C", timeout_s=10)
    assert response.status == "unavailable" and response.reason == reason


# ------------------------------------------------------------------ Codex


CODEX_OK = lines(
    {"type": "thread.started"},
    {"type": "item.completed", "item": {"type": "reasoning", "text": "private musing"}},
    {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(ANSWER)}},
    {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 7}},
)


def test_codex_is_ephemeral_with_every_extension_off_and_answers(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canned = use(monkeypatch, Canned((0, CODEX_OK, "")))
    backend = codex(tmp_path, credential)
    response = backend.deliberate("INSTRUCTION", "CONTEXT", timeout_s=10)
    argv = canned.argv[0]
    for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--json"):
        assert flag in argv, flag
    disabled = {argv[i + 1] for i, a in enumerate(argv) if a == "--disable"}
    assert disabled == set(CODEX_DISABLED_FEATURES) and "shell_tool" in disabled
    assert 'web_search="disabled"' in argv
    assert canned.stdin == ["INSTRUCTION\n\nCONTEXT"]
    assert response.status == "answered" and json.loads(response.text) == ANSWER
    assert backend.budget.output_tokens == 7


@pytest.mark.parametrize(
    "kind", ["command_execution", "mcp_tool_call", "web_search", "file_change", "todo_list"]
)
def test_a_codex_tool_event_is_a_sterility_failure_and_keeps_no_reasoning(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    stream = lines(
        {"type": "item.completed", "item": {"type": "reasoning", "text": "private musing"}},
        {"type": "item.started", "item": {"type": kind, "command": "cat ~/.bashrc"}},
    )
    use(monkeypatch, Canned((0, stream, "")))
    backend = codex(tmp_path, credential)
    with pytest.raises(SterilityFailure) as raised:
        backend.deliberate("I", "C", timeout_s=10)
    assert raised.value.category == f"item_{kind}"
    (quarantined,) = (tmp_path / "quarantine").iterdir()
    assert "private musing" not in quarantined.read_text(encoding="utf-8")


def test_codex_over_quota_is_unavailable(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch, Canned((1, "", "stream error: 429 Too Many Requests")))
    response = codex(tmp_path, credential).deliberate("I", "C", timeout_s=10)
    assert response.status == "unavailable" and response.reason == "quota"


# ----------------------------------------------------------------- budget


def test_the_budget_is_enforced_before_anything_is_spawned(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canned = use(monkeypatch, Canned((0, CLAUDE_OK, ""), (0, CLAUDE_OK, "")))
    backend = claude(tmp_path, credential, budget=2)
    backend.deliberate("I", "C", timeout_s=10)
    backend.deliberate("I", "C", timeout_s=10)
    with pytest.raises(BudgetExhausted):
        backend.deliberate("I", "C", timeout_s=10)
    assert len(canned.argv) == 2
    assert backend.budget.to_json()["attempted"] == 2


def test_a_sterility_failure_is_journalled_as_a_rejected_answer(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from person_cognition.deliberation import Deliberator, build_context

    use(
        monkeypatch,
        Canned((0, lines({"type": "system", "subtype": "init", "tools": ["Bash"]}), "")),
    )
    recorded: list[tuple[str, dict[str, Any]]] = []
    deliberator = Deliberator(
        mode="record_only",
        model=claude(tmp_path, credential),
        record=lambda kind, payload: recorded.append((kind, payload)),
    )
    context = build_context(
        reason="reflection",
        self_knowledge=None,
        world_available=None,
        situation=(),
        place=None,
        working_memory=[],
        beliefs=[],
        hypotheses=[],
        goals=[],
        projects=[],
        recent=[],
        capabilities=[],
        vocabulary={},
    )
    outcome = deliberator.deliberate(context, experienced_tick=0)
    assert outcome is not None and outcome.verdict is None
    kind, payload = recorded[-1]
    assert kind == "deliberation_completed" and payload["verdict"] == "rejected"
    assert payload["rejections"] == ["sterility_failure:tools_exposed"]
    assert payload["proposal"] is None and "Bash" not in json.dumps(payload)


# --------------------------------------------------------------- sandbox


def _bubblewrap_works() -> bool:
    if shutil.which("bwrap") is None:
        return False
    try:
        done = subprocess.run(
            [
                "bwrap",
                "--ro-bind",
                "/usr",
                "/usr",
                "--symlink",
                "usr/bin",
                "/bin",
                "--symlink",
                "usr/lib",
                "/lib",
                "--symlink",
                "usr/lib",
                "/lib64",
                "--unshare-all",
                "/usr/bin/true",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


@pytest.mark.skipif(not _bubblewrap_works(), reason="bubblewrap unavailable here")
def test_the_sandbox_sees_none_of_the_host_and_only_the_one_credential(
    credential: Path,
) -> None:
    report = self_check([Credential(credential, ".claude/.credentials.json")])
    assert report["exit"] == 0
    assert report["visible"] == [], "no home, repository, /home, /root or /run/user"
    assert report["hostname"] == "person-sandbox", "the machine's name stays outside"
    assert report["home_entries"] == [
        "/sandbox/home/.claude",
        "/sandbox/home/.claude/.credentials.json",
    ]
    assert set(report["environment"]) <= {"HOME", "LANG", "PATH", "PWD", "SHLVL", "TMPDIR", "_"}
    assert os.environ.get("HOME") not in json.dumps(report)


def test_a_known_codex_diagnostic_is_not_a_capability(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notice = (
        "Code Mode is unavailable because code-mode host is disabled. "
        "Code mode will fail closed; enable `features.code_mode_host`."
    )
    stream = lines(
        {"type": "item.completed", "item": {"type": "error", "message": notice}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(ANSWER)}},
        {"type": "turn.completed", "usage": {"input_tokens": 18000, "output_tokens": 500}},
    )
    use(monkeypatch, Canned((0, stream, "")))
    backend = codex(tmp_path, credential)
    response = backend.deliberate("I", "C", timeout_s=10)
    assert response.status == "answered" and backend.disabled is None
    assert backend.diagnostics and response.harness == "codex_exec"
    assert response.opaque_harness and response.input_tokens == 18000


@pytest.mark.parametrize(
    "item",
    [
        {"type": "error", "message": "something nobody has seen before"},
        {"type": "brand_new_item_kind"},
    ],
)
def test_an_unknown_codex_event_degrades_only_that_answer(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch, item: dict[str, Any]
) -> None:
    from person_cognition.deliberation import ProviderDegraded

    stream = lines(
        {"type": "item.completed", "item": item},
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(ANSWER)}},
    )
    use(monkeypatch, Canned((0, stream, ""), (0, CODEX_OK, "")))
    backend = codex(tmp_path, credential)
    with pytest.raises(ProviderDegraded):
        backend.deliberate("I", "C", timeout_s=10)
    assert backend.disabled is None, "not a sterility failure"
    assert backend.deliberate("I", "C", timeout_s=10).status == "answered"


# ------------------------------------------------------------- app-server


def app_server(tmp_path: Path, credential: Path, session: list[dict[str, Any]]) -> Any:
    from person_cognition.deliberation.providers import CodexAppServerModel

    backend = CodexAppServerModel(
        model="codex-test",
        budget=CallBudget(5),
        quarantine=tmp_path / "quarantine",
        credentials=credential,
    )
    backend._session = lambda instruction, context: (session, "", 0)  # type: ignore[method-assign]
    return backend


def completed(item: dict[str, Any]) -> dict[str, Any]:
    return {"method": "item/completed", "params": {"item": item}}


def test_the_app_server_answers_with_our_instruction_as_its_base(
    tmp_path: Path, credential: Path
) -> None:
    from person_cognition.deliberation.providers import CodexAppServerModel

    argv = CodexAppServerModel(
        model="m", budget=CallBudget(1), quarantine=tmp_path, credentials=credential
    ).app_argv()
    assert "shell_tool" in argv and 'web_search="disabled"' in argv
    backend = app_server(
        tmp_path,
        credential,
        [
            {"id": 1, "result": {}},
            {"id": 2, "result": {"thread": {"id": "t"}}},
            completed({"type": "reasoning"}),
            completed({"type": "agentMessage", "text": json.dumps(ANSWER)}),
            {
                "method": "thread/tokenUsage/updated",
                "params": {"tokenUsage": {"last": {"inputTokens": 5127, "outputTokens": 259}}},
            },
            {"method": "turn/completed", "params": {}},
        ],
    )
    response = backend.deliberate("I", "C", timeout_s=10)
    assert response.status == "answered" and response.harness == "codex_app_server"
    assert response.input_tokens == 5127 and json.loads(response.text) == ANSWER


@pytest.mark.parametrize("kind", ["commandExecution", "mcpToolCall", "webSearch", "plan", "sleep"])
def test_an_app_server_tool_item_is_a_sterility_failure(
    tmp_path: Path, credential: Path, kind: str
) -> None:
    backend = app_server(
        tmp_path,
        credential,
        [
            {"id": 2, "result": {"thread": {"id": "t"}}},
            completed({"type": kind, "command": "ls ~"}),
        ],
    )
    with pytest.raises(SterilityFailure):
        backend.deliberate("I", "C", timeout_s=10)
    assert backend.disabled is not None
    (quarantined,) = (tmp_path / "quarantine").iterdir()
    assert "ls ~" not in quarantined.read_text(encoding="utf-8"), "only the stream's shape"


def test_an_app_server_refusal_is_unavailable(tmp_path: Path, credential: Path) -> None:
    backend = app_server(
        tmp_path, credential, [{"id": 2, "error": {"code": -32000, "message": "not logged in"}}]
    )
    assert backend.deliberate("I", "C", timeout_s=10).status == "unavailable"


def test_without_bubblewrap_no_sterile_backend_runs(
    tmp_path: Path, credential: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sterile_module.shutil, "which", lambda name: None)
    with pytest.raises(SterilityError, match="bubblewrap"):
        claude(tmp_path, credential).deliberate("I", "C", timeout_s=10)
