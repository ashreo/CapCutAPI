#!/usr/bin/env python3
"""Minimal stdio smoke test for the CapCut MCP server.

Drives mcp_server.py over line-delimited JSON-RPC exactly the way an MCP client
does, and prints server stderr so failures are visible. Deliberately does NOT
set PYTHONIOENCODING, so it reproduces the default Windows launch environment.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(HERE, "venv-capcut", "Scripts", "python.exe")
if not os.path.exists(PYTHON):
    PYTHON = os.path.join(HERE, "venv-capcut", "bin", "python")


def main():
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)

    proc = subprocess.Popen(
        [PYTHON, os.path.join(HERE, "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=HERE,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    next_id = [0]

    def call(method, params=None):
        next_id[0] += 1
        req = {"jsonrpc": "2.0", "id": next_id[0], "method": method}
        if params is not None:
            req["params"] = params
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line.strip():
            raise RuntimeError(f"empty response to {method}")
        return json.loads(line)

    def tool(name, args):
        resp = call("tools/call", {"name": name, "arguments": args})
        text = resp["result"]["content"][0]["text"]
        return json.loads(text)

    failures = []
    try:
        call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "1.0"},
        })
        tools = call("tools/list")["result"]["tools"]
        print(f"[1] tools/list -> {len(tools)} tools")
        if len(tools) != 11:
            failures.append(f"expected 11 tools, got {len(tools)}")

        draft = tool("create_draft", {"width": 1080, "height": 1920})
        if not draft.get("success"):
            failures.append(f"create_draft failed: {draft}")
            raise SystemExit
        draft_id = draft["result"]["draft_id"]
        print(f"[2] create_draft 1080x1920 -> {draft_id}")

        txt = tool("add_text", {
            "draft_id": draft_id,
            "text": "NEON CHAOS TEST",
            "start": 0,
            "end": 3,
            "font_size": 48,
            "font_color": "#00ffff",
        })
        print(f"[3] add_text -> success={txt.get('success')}")
        if not txt.get("success"):
            failures.append(f"add_text failed: {txt}")

        # Non-ASCII round trip: this is what used to kill the pipe on Windows.
        bad = tool("add_video", {"draft_id": draft_id,
                                 "video_url": "https://example.com/none.mp4",
                                 "start": 0, "end": 1,
                                 "transition": "definitely_not_a_transition"})
        print(f"[4] non-ASCII error round-trip survived -> success={bad.get('success')}")

        saved = tool("save_draft", {"draft_id": draft_id})
        print(f"[5] save_draft -> success={saved.get('success')}")
        if not saved.get("success"):
            failures.append(f"save_draft failed: {saved}")
        else:
            folder = os.path.join(HERE, draft_id)
            print(f"    folder exists: {os.path.isdir(folder)} -> {folder}")
            if not os.path.isdir(folder):
                failures.append("save_draft reported success but no dfd_ folder")
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait(timeout=15)
        err = proc.stderr.read()
        if err:
            print("\n--- server stderr (tail) ---")
            print("\n".join(err.strip().splitlines()[-15:]))

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
