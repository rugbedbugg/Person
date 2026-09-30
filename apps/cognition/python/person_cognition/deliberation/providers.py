"""Subscription-backed provider backends, sterile and stateless (ADR 0020, C2).

Each call is one fresh subprocess in its own sterile sandbox (`sterile.py`),
with every provider tool switched off at the provider itself, no session
persisted, and a hard budget checked before anything is spawned. The event
stream is inspected: a tool offered or used where none may exist is a
sterility failure, which rejects the answer, quarantines the raw output
outside anything committed, and disables the backend until investigated.
Reasoning text a provider emits is never kept.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import ModelResponse, ProviderDegraded, SterilityFailure, canonical_json, sha256_text
from .proposal import PROPOSAL_JSON_SCHEMA
from .sterile import PROFILE_VERSION, SANDBOX_HOME, SANDBOX_WORK, Credential, sterile

#: Stderr patterns, lowercased, that say why a provider gave no answer.
QUOTA = re.compile(r"rate.?limit|quota|usage limit|too many requests|429")
AUTHENTICATION = re.compile(r"not logged in|log ?in|unauthori[sz]ed|authenticat|401|403|expired")


class BudgetExhausted(RuntimeError):
    """The call budget was spent before this call. Nothing was spawned."""


@dataclass
class CallBudget:
    """A hard cap on provider calls, enforced before any process starts."""

    max_calls: int
    attempted: int = 0
    completed: int = 0
    rejected: int = 0
    unavailable: int = 0
    sterility_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def spend(self) -> None:
        if self.attempted >= self.max_calls:
            raise BudgetExhausted(f"provider call budget of {self.max_calls} is spent")
        self.attempted += 1

    def to_json(self) -> dict[str, int]:
        return {
            "max_calls": self.max_calls,
            "attempted": self.attempted,
            "completed": self.completed,
            "rejected": self.rejected,
            "unavailable": self.unavailable,
            "sterility_failures": self.sterility_failures,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass
class Backend(ABC):
    """What every sterile backend shares: budget, quarantine, disabling."""

    model: str
    budget: CallBudget
    quarantine: Path
    timeout_s: float = 180.0
    disabled: str | None = None
    #: Tool names each call exposed, for the probe record.
    exposed: list[list[str]] = field(default_factory=list)
    #: Known provider diagnostics seen (capabilities withheld, not used).
    diagnostics: list[str] = field(default_factory=list)
    _turn_input: int = 0
    _turn_output: int = 0

    def _unavailable(self, reason: str, started: float, version: str) -> ModelResponse:
        self.budget.unavailable += 1
        return ModelResponse(
            status="unavailable",
            provider=self.provider_name(),
            model=self.model,
            backend_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            reason=reason,
        )

    def _classify(self, stderr: str) -> str:
        lowered = stderr.lower()
        if QUOTA.search(lowered):
            return "quota"
        if AUTHENTICATION.search(lowered):
            return "authentication"
        return "backend"

    def _sterility_failure(self, category: str, raw: str) -> None:
        """Quarantine the raw output locally, disable, and refuse the answer."""
        self.budget.sterility_failures += 1
        self.disabled = category
        self.quarantine.mkdir(parents=True, exist_ok=True, mode=0o700)
        digest = sha256_text(raw)
        target = self.quarantine / f"sterility-failure-{digest[:16]}.txt"
        descriptor = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(raw)
        raise SterilityFailure(self.provider_name(), category, digest)

    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def _call(self, instruction: str, context: str) -> ModelResponse: ...

    def deliberate(self, instruction: str, context: str, *, timeout_s: float) -> ModelResponse:
        if self.disabled is not None:
            raise SterilityFailure(self.provider_name(), f"disabled_{self.disabled}", None)
        self.budget.spend()
        self.timeout_s = min(self.timeout_s, timeout_s)
        return self._call(instruction, context)


def _events(stdout: str) -> list[dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


class ClaudeCodeModel(Backend):
    """Claude Code in print mode: no tools, no MCP, no settings, no session."""

    provider = "claude-code"
    #: Tools the CLI itself adds to carry a JSON-schema answer. Not a capability.
    STRUCTURAL_TOOLS = frozenset({"StructuredOutput"})

    def __init__(
        self,
        *,
        model: str,
        budget: CallBudget,
        quarantine: Path,
        credentials: Path | None = None,
        executable: str = "/usr/bin/claude",
        cli_version: str = "unknown",
    ) -> None:
        super().__init__(model=model, budget=budget, quarantine=quarantine)
        self.credentials = credentials or Path.home() / ".claude" / ".credentials.json"
        self.executable = executable
        self.cli_version = cli_version

    def provider_name(self) -> str:
        return self.provider

    def argv(self, instruction: str) -> list[str]:
        return [
            self.executable,
            "-p",
            "--no-session-persistence",
            "--tools",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--system-prompt",
            instruction,
            "--output-format",
            "stream-json",
            "--verbose",
            "--json-schema",
            canonical_json(PROPOSAL_JSON_SCHEMA),
            "--model",
            self.model,
        ]

    def _call(self, instruction: str, context: str) -> ModelResponse:
        version = f"claude-code {self.cli_version}; {PROFILE_VERSION}"
        started = time.monotonic()
        try:
            with sterile(
                [Credential(self.credentials, ".claude/.credentials.json")],
                extra_environment={"CLAUDE_CONFIG_DIR": f"{SANDBOX_HOME}/.claude"},
            ) as sandbox:
                done = sandbox.run(self.argv(instruction), stdin=context, timeout_s=self.timeout_s)
        except subprocess.TimeoutExpired:
            return self._unavailable("timeout", started, version)
        events = _events(done.stdout)
        for event in events:
            if event.get("type") == "system" and event.get("subtype") == "init":
                tools = [str(tool) for tool in event.get("tools", [])]
                self.exposed.append(tools)
                if set(tools) - self.STRUCTURAL_TOOLS or event.get("mcp_servers"):
                    self._sterility_failure("tools_exposed", done.stdout)
                if event.get("cwd") not in (None, SANDBOX_WORK):
                    self._sterility_failure("unexpected_cwd", done.stdout)
            if event.get("type") == "assistant":
                for part in event.get("message", {}).get("content", []):
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "tool_use"
                        and part.get("name") not in self.STRUCTURAL_TOOLS
                    ):
                        self._sterility_failure("tool_used", done.stdout)
        result = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if result is None or result.get("is_error"):
            return self._unavailable(self._classify(done.stderr + done.stdout), started, version)
        usage = result.get("usage") or {}
        # Cached input is still input the call carried.
        spent_in = sum(
            int(usage.get(key) or 0)
            for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        )
        spent_out = int(usage.get("output_tokens") or 0)
        self.budget.input_tokens += spent_in
        self.budget.output_tokens += spent_out
        structured = result.get("structured_output")
        text = (
            canonical_json(structured) if structured is not None else str(result.get("result", ""))
        )
        self.budget.completed += 1
        return ModelResponse(
            status="answered",
            provider=self.provider,
            model=self.model,
            backend_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            text=text,
            # The CLI adds its own structured-output carrier to our system
            # prompt, and the full request is not visible to us.
            harness="claude_code_print",
            provider_owned_harness=True,
            opaque_harness=True,
            input_tokens=spent_in,
            output_tokens=spent_out,
        )


#: Every Codex capability switched off, beyond the shell (codex-cli 0.159).
CODEX_DISABLED_FEATURES: tuple[str, ...] = (
    "shell_tool",
    "unified_exec",
    "unified_exec_tty",
    "shell_snapshot",
    "apps",
    "plugins",
    "plugin_sharing",
    "remote_plugin",
    "hooks",
    "multi_agent",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "code_mode_host",
    "image_generation",
    "view_image",
    "goals",
    "skill_search",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "sleep_tool",
    "workspace_dependencies",
    "worktrees",
    "mentions_v2",
    "tool_call_mcp_elicitation",
    "daemon_auto_start",
    "realtime_conversation",
)

#: How a Codex event item is read. Messages carry the answer. Tool and
#: capability items mean something acted, which a sterile backend cannot do:
#: a sterility failure that disables it. A provider diagnostic acts on
#: nothing; a known one passes, an unknown one degrades only this answer.
#: Any other item type is unknown, and degrades only this answer too.
CODEX_MESSAGE_ITEMS = frozenset({"agent_message", "reasoning"})
CODEX_TOOL_ITEMS = frozenset(
    {
        "command_execution",
        "mcp_tool_call",
        "web_search",
        "file_change",
        "todo_list",
        "collab_tool_call",
        "image_generation",
        "view_image",
    }
)
#: Diagnostics that report a capability being withheld, not exercised.
KNOWN_DIAGNOSTICS: tuple[re.Pattern[str], ...] = (
    re.compile(r"code mode is unavailable because code-mode host is disabled", re.IGNORECASE),
)


def classify_codex_item(item: dict[str, Any]) -> str:
    """`message`, `diagnostic`, `unknown_diagnostic`, `tool` or `unknown`."""
    kind = str(item.get("type"))
    if kind in CODEX_MESSAGE_ITEMS:
        return "message"
    if kind in CODEX_TOOL_ITEMS:
        return "tool"
    if kind == "error":
        message = str(item.get("message", ""))
        known = any(pattern.search(message) for pattern in KNOWN_DIAGNOSTICS)
        return "diagnostic" if known else "unknown_diagnostic"
    return "unknown"


class CodexModel(Backend):
    """Codex `exec`, ephemeral, with every tool and extension switched off."""

    provider = "codex"

    def __init__(
        self,
        *,
        model: str,
        budget: CallBudget,
        quarantine: Path,
        credentials: Path | None = None,
        executable: str = "/usr/bin/codex",
        cli_version: str = "unknown",
    ) -> None:
        super().__init__(model=model, budget=budget, quarantine=quarantine)
        self.credentials = credentials or Path.home() / ".codex" / "auth.json"
        self.executable = executable
        self.cli_version = cli_version

    def provider_name(self) -> str:
        return self.provider

    def argv(self) -> list[str]:
        argv = [
            self.executable,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--cd",
            SANDBOX_WORK,
            "--output-schema",
            f"{SANDBOX_WORK}/schema.json",
            "--model",
            self.model,
            "--config",
            'web_search="disabled"',
        ]
        for feature in CODEX_DISABLED_FEATURES:
            argv += ["--disable", feature]
        return [*argv, "-"]

    def _call(self, instruction: str, context: str) -> ModelResponse:
        version = f"codex {self.cli_version}; {PROFILE_VERSION}"
        started = time.monotonic()
        try:
            with sterile(
                [Credential(self.credentials, ".codex/auth.json")],
                extra_environment={"CODEX_HOME": f"{SANDBOX_HOME}/.codex"},
            ) as sandbox:
                (sandbox.root / "work" / "schema.json").write_text(
                    canonical_json(PROPOSAL_JSON_SCHEMA), encoding="utf-8"
                )
                done = sandbox.run(
                    self.argv(), stdin=f"{instruction}\n\n{context}", timeout_s=self.timeout_s
                )
        except subprocess.TimeoutExpired:
            return self._unavailable("timeout", started, version)
        events = _events(done.stdout)
        message: str | None = None
        degraded: str | None = None
        for event in events:
            item = event.get("item")
            if isinstance(item, dict) and event.get("type", "").startswith("item."):
                kind = str(item.get("type"))
                verdict = classify_codex_item(item)
                if verdict == "tool":
                    self._sterility_failure(f"item_{kind}", _without_reasoning(events))
                if verdict == "diagnostic":
                    self.diagnostics.append(str(item.get("message", ""))[:200])
                if verdict in ("unknown", "unknown_diagnostic"):
                    degraded = degraded or f"{verdict}_{kind}"
                if kind == "agent_message" and event.get("type") == "item.completed":
                    message = str(item.get("text", ""))
            if event.get("type") == "turn.completed":
                usage = event.get("usage") or {}
                self._turn_input = int(usage.get("input_tokens") or 0)
                self._turn_output = int(usage.get("output_tokens") or 0)
                self.budget.input_tokens += self._turn_input
                self.budget.output_tokens += self._turn_output
        if done.returncode != 0 or message is None:
            return self._unavailable(self._classify(done.stderr + done.stdout), started, version)
        if degraded is not None:
            self.budget.rejected += 1
            raise ProviderDegraded(self.provider, degraded)
        self.budget.completed += 1
        return ModelResponse(
            status="answered",
            provider=self.provider,
            model=self.model,
            backend_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            text=message,
            harness="codex_exec",
            provider_owned_harness=True,
            opaque_harness=True,
            input_tokens=self._turn_input,
            output_tokens=self._turn_output,
        )


def _without_reasoning(events: Sequence[dict[str, Any]]) -> str:
    """The event stream with reasoning text removed: none of it is kept."""
    kept = []
    for event in events:
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "reasoning":
            event = {**event, "item": {"type": "reasoning", "text": "[omitted]"}}
        kept.append(event)
    return "\n".join(json.dumps(event) for event in kept)


#: App-server (protocol v2) thread items. Messages carry or accompany the
#: answer; every other known kind is something acting, which a sterile
#: backend cannot do.
APP_SERVER_MESSAGE_ITEMS = frozenset({"userMessage", "agentMessage", "reasoning"})
APP_SERVER_TOOL_ITEMS = frozenset(
    {
        "hookPrompt",
        "functionCallOutput",
        "plan",
        "commandExecution",
        "fileChange",
        "mcpToolCall",
        "dynamicToolCall",
        "collabAgentToolCall",
        "subAgentActivity",
        "webSearch",
        "imageView",
        "sleep",
        "imageGeneration",
        "enteredReviewMode",
        "exitedReviewMode",
    }
)


class CodexAppServerModel(CodexModel):
    """Codex through the official app-server, with our instruction as its base.

    One ephemeral thread per call whose `baseInstructions` is the deliberation
    instruction template, so the coding agent's own system prompt is replaced
    rather than prepended. Authentication stays entirely inside the official
    process; nothing here touches the token.
    """

    provider = "codex"

    def app_argv(self) -> list[str]:
        argv = [self.executable, "app-server", "--listen", "stdio://"]
        for feature in CODEX_DISABLED_FEATURES:
            argv += ["--disable", feature]
        return [*argv, "--config", 'web_search="disabled"']

    def _session(
        self, instruction: str, context: str | None
    ) -> tuple[list[dict[str, Any]], str, int]:
        """Run the protocol; with no context, stop before any model turn."""
        with sterile(
            [Credential(self.credentials, ".codex/auth.json")],
            extra_environment={"CODEX_HOME": f"{SANDBOX_HOME}/.codex"},
        ) as sandbox:
            process = sandbox.popen(self.app_argv())
            seen: list[dict[str, Any]] = []
            deadline = time.monotonic() + self.timeout_s
            assert process.stdin is not None and process.stdout is not None

            def send(message: dict[str, Any]) -> None:
                assert process.stdin is not None
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()

            def until(done: Any) -> dict[str, Any] | None:
                import selectors

                selector = selectors.DefaultSelector()
                assert process.stdout is not None
                selector.register(process.stdout, selectors.EVENT_READ)
                try:
                    while time.monotonic() < deadline:
                        if not selector.select(timeout=max(0.0, deadline - time.monotonic())):
                            break
                        line = process.stdout.readline()
                        if not line:
                            return None
                        try:
                            message: dict[str, Any] = json.loads(line)
                        except ValueError:
                            continue
                        if not isinstance(message, dict):
                            continue
                        seen.append(message)
                        if done(message):
                            return message
                finally:
                    selector.close()
                raise subprocess.TimeoutExpired(self.app_argv(), self.timeout_s)

            try:
                send(
                    {
                        "id": 1,
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "person-deliberation", "version": "c2"}},
                    }
                )
                until(lambda m: m.get("id") == 1)
                send({"method": "initialized"})
                send(
                    {
                        "id": 2,
                        "method": "thread/start",
                        "params": {
                            "baseInstructions": instruction,
                            "developerInstructions": "",
                            "ephemeral": True,
                            "model": self.model,
                            "cwd": SANDBOX_WORK,
                            "sandbox": "read-only",
                            "approvalPolicy": "never",
                        },
                    }
                )
                started = until(lambda m: m.get("id") == 2)
                thread = ((started or {}).get("result") or {}).get("thread", {}).get("id")
                if context is None or thread is None:
                    return seen, "", 0 if thread else 1
                send(
                    {
                        "id": 3,
                        "method": "turn/start",
                        "params": {
                            "threadId": thread,
                            "input": [{"type": "text", "text": context}],
                            "outputSchema": PROPOSAL_JSON_SCHEMA,
                        },
                    }
                )
                until(lambda m: m.get("method") == "turn/completed")
                return seen, "", 0
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                stderr = process.stderr.read() if process.stderr else ""
                seen.append({"_stderr_chars": len(stderr or "")})

    def handshake(self) -> dict[str, Any]:
        """Initialize and start an ephemeral thread, and stop: no model turn."""
        seen, _, code = self._session("handshake only", None)
        return {"code": code, "methods": [m.get("method") or f"result:{m.get('id')}" for m in seen]}

    def _call(self, instruction: str, context: str) -> ModelResponse:
        version = f"codex app-server {self.cli_version}; {PROFILE_VERSION}"
        started = time.monotonic()
        try:
            seen, _, code = self._session(instruction, context)
        except subprocess.TimeoutExpired:
            return self._unavailable("timeout", started, version)
        message: str | None = None
        degraded: str | None = None
        tokens = (0, 0)
        for event in seen:
            method = event.get("method")
            params = event.get("params") or {}
            if method == "error":
                text = json.dumps(params)
                known = any(p.search(text) for p in KNOWN_DIAGNOSTICS)
                if known:
                    self.diagnostics.append(text[:200])
                else:
                    degraded = degraded or "unknown_diagnostic_error"
            if method in ("item/started", "item/completed"):
                item = params.get("item") or {}
                kind = str(item.get("type"))
                if kind in APP_SERVER_TOOL_ITEMS:
                    # Only the shape of the stream is quarantined: no text.
                    self._sterility_failure(
                        f"item_{kind}",
                        json.dumps(
                            [
                                {
                                    "method": m.get("method"),
                                    "item": ((m.get("params") or {}).get("item") or {}).get("type"),
                                }
                                for m in seen
                            ]
                        ),
                    )
                elif kind not in APP_SERVER_MESSAGE_ITEMS:
                    degraded = degraded or f"unknown_{kind}"
                if kind == "agentMessage" and method == "item/completed":
                    message = str(item.get("text", ""))
            if method == "thread/tokenUsage/updated":
                last = (params.get("tokenUsage") or {}).get("last") or {}
                tokens = (int(last.get("inputTokens") or 0), int(last.get("outputTokens") or 0))
        refused = any("error" in m for m in seen if m.get("id") in (1, 2, 3))
        if refused or message is None:
            return self._unavailable("backend", started, version)
        self._turn_input, self._turn_output = tokens
        self.budget.input_tokens += tokens[0]
        self.budget.output_tokens += tokens[1]
        if degraded is not None:
            self.budget.rejected += 1
            raise ProviderDegraded(self.provider, degraded)
        self.budget.completed += 1
        return ModelResponse(
            status="answered",
            provider=self.provider,
            model=self.model,
            backend_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            text=message,
            harness="codex_app_server",
            provider_owned_harness=True,
            opaque_harness=True,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
        )
