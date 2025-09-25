#!/usr/bin/env python3
"""Minimal example app using CodexClient.

Usage:
  python examples/basic_conversation.py "Add a smoke test"

Flags:
  --model MODEL                  Model slug (default: gpt-5)
  --sandbox {read-only,workspace-write,danger-full-access}
  --approval {untrusted,on-failure,on-request,never}
  --auto-approve                 Auto‑approve exec/patch requests
  --exit-on-complete             Exit after the first completed turn (default: prompt for another turn)
  --allow-apply-patch            Enable the apply patch tool (disabled by default)

This script starts a stateful conversation, submits one user turn, then streams
events to stdout. For approval requests, it either auto‑approves (when the flag
is set) or prompts interactively.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, cast

from codex import CodexClient, CodexConfig
from codex.config import ApprovalPolicy, SandboxMode
from codex.protocol.types import ReviewDecision


def _etype(ev: Any) -> str:
    msg = getattr(ev, "msg", None)
    root = getattr(msg, "root", None)
    if root is not None and hasattr(root, "type"):
        val = root.type
        return cast(str, val) if isinstance(val, str) else "unknown"
    if isinstance(msg, dict):
        return cast("str", msg.get("type", "unknown"))
    return getattr(msg, "type", "unknown") or "unknown"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CodexClient example")
    p.add_argument("prompt", help="User prompt to send as a turn")
    p.add_argument("--model", default="gpt-5")
    p.add_argument(
        "--sandbox",
        choices=["read-only", "workspace-write", "danger-full-access"],
        default="workspace-write",
    )
    p.add_argument(
        "--approval",
        choices=["untrusted", "on-failure", "on-request", "never"],
        default="on-request",
    )
    p.add_argument("--auto-approve", action="store_true")
    p.add_argument("--exit-on-complete", action="store_true")
    p.add_argument("--allow-apply-patch", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    # Map to enums for clarity (strings would also work)
    sandbox_map = {
        "read-only": SandboxMode.READ_ONLY,
        "workspace-write": SandboxMode.WORKSPACE_WRITE,
        "danger-full-access": SandboxMode.DANGER_FULL_ACCESS,
    }
    approval_map = {
        "untrusted": ApprovalPolicy.UNTRUSTED,
        "on-failure": ApprovalPolicy.ON_FAILURE,
        "on-request": ApprovalPolicy.ON_REQUEST,
        "never": ApprovalPolicy.NEVER,
    }

    cfg = CodexConfig(
        model=args.model,
        include_apply_patch_tool=bool(args.allow_apply_patch),  # default: disabled
    )
    client = CodexClient(config=cfg)
    conv = client.start_conversation()

    # Send the initial turn with per‑turn overrides.
    conv.submit_user_turn(
        args.prompt,
        sandbox_mode=sandbox_map[args.sandbox],
        approval_policy=approval_map[args.approval],
    )

    print("[codex] streaming events...", flush=True)
    for ev in conv:
        et = _etype(ev)

        if et == "session_configured":
            model = getattr(getattr(ev.msg, "root", ev.msg), "model", "?")
            print(f"session configured (model={model})")

        elif et == "agent_message":
            msg = getattr(getattr(ev.msg, "root", ev.msg), "message", "")
            print(f"assistant: {msg}")

        elif et == "agent_message_delta":
            delta = getattr(getattr(ev.msg, "root", ev.msg), "delta", "")
            print(delta, end="", flush=True)

        # Tool-call logging: MCP tools, exec, web search, and patch apply
        elif et == "mcp_tool_call_begin":
            root = getattr(ev.msg, "root", ev.msg)
            inv = getattr(root, "invocation", None)
            server = getattr(inv, "server", "?")
            tool = getattr(inv, "tool", "?")
            mcp_args = getattr(inv, "arguments", None)
            call_id = getattr(root, "call_id", "?")
            print(f"[tool] mcp begin id={call_id} {server}:{tool} args={mcp_args}")

        elif et == "mcp_tool_call_end":
            root = getattr(ev.msg, "root", ev.msg)
            inv = getattr(root, "invocation", None)
            server = getattr(inv, "server", "?")
            tool = getattr(inv, "tool", "?")
            call_id = getattr(root, "call_id", "?")
            duration = getattr(root, "duration", None)
            res = getattr(root, "result", None)
            ok = getattr(res, "Ok", None)
            err = getattr(res, "Err", None)
            if err is not None:
                print(
                    f"[tool] mcp end   id={call_id} {server}:{tool} ERROR: {err} (duration={duration})"
                )
            else:
                # Avoid printing large payloads; just show a short summary if present
                out_type = getattr(ok, "type", None) if ok is not None else None
                print(
                    f"[tool] mcp end   id={call_id} {server}:{tool} ok type={out_type} (duration={duration})"
                )

        elif et == "exec_command_begin":
            root = getattr(ev.msg, "root", ev.msg)
            cmd = getattr(root, "command", [])
            cwd = getattr(root, "cwd", "")
            call_id = getattr(root, "call_id", "?")
            print(f"[tool] exec begin id={call_id} cwd={cwd} cmd={' '.join(cmd)}")

        elif et == "exec_command_end":
            root = getattr(ev.msg, "root", ev.msg)
            call_id = getattr(root, "call_id", "?")
            exit_code = getattr(root, "exit_code", "?")
            duration = getattr(root, "duration", None)
            stdout = getattr(root, "stdout", "") or ""
            stderr = getattr(root, "stderr", "") or ""
            print(
                f"[tool] exec end   id={call_id} exit={exit_code} duration={duration} stdout={len(stdout)}B stderr={len(stderr)}B"
            )

        elif et == "web_search_begin":
            call_id = getattr(getattr(ev.msg, "root", ev.msg), "call_id", "?")
            print(f"[tool] web_search begin id={call_id}")

        elif et == "web_search_end":
            root = getattr(ev.msg, "root", ev.msg)
            call_id = getattr(root, "call_id", "?")
            query = getattr(root, "query", "?")
            print(f"[tool] web_search end   id={call_id} query={query}")

        elif et == "patch_apply_begin":
            root = getattr(ev.msg, "root", ev.msg)
            call_id = getattr(root, "call_id", "?")
            auto = getattr(root, "auto_approved", False)
            changes = getattr(root, "changes", {}) or {}
            print(
                f"[tool] patch begin id={call_id} files={len(changes)} auto_approved={bool(auto)}"
            )

        elif et == "patch_apply_end":
            root = getattr(ev.msg, "root", ev.msg)
            call_id = getattr(root, "call_id", "?")
            success = getattr(root, "success", False)
            print(f"[tool] patch end   id={call_id} success={bool(success)}")

        elif et == "exec_approval_request":
            root = getattr(ev.msg, "root", ev.msg)
            cmd = getattr(root, "command", [])
            cwd = getattr(root, "cwd", "")
            print("\n[approval request] exec:", cmd, "in", cwd)
            if args.auto_approve or _prompt_yes_no("Approve exec? [y/N] "):
                conv.approve_exec(ev.id, ReviewDecision.approved)
            else:
                conv.approve_exec(ev.id, ReviewDecision.denied)

        elif et == "apply_patch_approval_request":
            print("\n[approval request] apply_patch")
            if args.auto_approve or _prompt_yes_no("Approve patch? [y/N] "):
                conv.approve_patch(ev.id, ReviewDecision.approved)
            else:
                conv.approve_patch(ev.id, ReviewDecision.denied)

        elif et == "task_complete":
            last = getattr(getattr(ev.msg, "root", ev.msg), "last_agent_message", None)
            if last:
                print("\n[task complete]", last)
            # Either exit immediately or allow the user to continue the conversation
            if args.exit_on_complete:
                conv.shutdown()
            else:
                try:
                    nxt = input("\nAnother prompt (blank to quit): ").strip()
                except (EOFError, KeyboardInterrupt):
                    nxt = ""
                if nxt:
                    conv.submit_user_turn(nxt)
                else:
                    conv.shutdown()

        elif et == "shutdown_complete":
            print("[codex] shutdown complete")
            break

        elif et == "stream_error":
            root = getattr(ev.msg, "root", ev.msg)
            print("[stream error]", getattr(root, "message", "?"))

    return 0


def _prompt_yes_no(prompt: str) -> bool:
    try:
        ans = input(prompt).strip().lower()
        return ans in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
