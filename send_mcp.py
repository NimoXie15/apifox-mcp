# -*- coding: utf-8 -*-
"""MCP 服务器 JSON-RPC 验证脚本：initialize → tools/list → tools/call list_api_endpoints"""
import json
import os
import queue
import subprocess
import sys
import threading

CMD = r"D:\files\apifox-mcp\venv\Scripts\python.exe"
ENV = os.environ.copy()
ENV.update({
    "APIFOX_TOKEN": os.environ.get("APIFOX_TOKEN", ""),      # 从环境变量读取，勿硬编码（防提交泄露）
    "APIFOX_PROJECT_ID": os.environ.get("APIFOX_PROJECT_ID", ""),  # 同上
    "APIFOX_MODULE_ID": os.environ.get("APIFOX_MODULE_ID", ""),    # 同上
    "PYTHONPATH": r"D:\files\apifox-mcp",
})
missing = [k for k in ("APIFOX_TOKEN", "APIFOX_PROJECT_ID", "APIFOX_MODULE_ID") if not ENV[k]]
if missing:
    sys.exit("错误: 请先设置环境变量 " + ", ".join(missing) + "\n"
             "例如: export APIFOX_TOKEN=<token> APIFOX_PROJECT_ID=<pid> APIFOX_MODULE_ID=<mid>")

proc = subprocess.Popen(
    [CMD, "-m", "src.main"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=ENV,
    text=True,
    bufsize=1,
)

msg_q = queue.Queue()


def read_stdout():
    for line in proc.stdout:
        msg_q.put(line)


def read_stderr():
    for line in proc.stderr:
        msg_q.put("STDERR: " + line)


threading.Thread(target=read_stdout, daemon=True).start()
threading.Thread(target=read_stderr, daemon=True).start()


def send(obj, timeout=30):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()
    # 收集直到收到 id 匹配的响应
    deadline = 0.0
    import time
    end = time.time() + timeout
    while time.time() < end:
        try:
            line = msg_q.get(timeout=1)
        except queue.Empty:
            continue
        line = line.strip()
        if not line or line.startswith("STDERR:"):
            print("  [log]", line[:200])
            continue
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            print("  [non-json]", line[:200])
            continue
        if resp.get("id") == obj["id"]:
            return resp
    return {"error": "timeout waiting for response"}


# 1. initialize
print("== initialize ==")
r = send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "test", "version": "1.0"}}})
print("  protocol:", r.get("result", {}).get("protocolVersion"))
print("  serverInfo:", r.get("result", {}).get("serverInfo"))

# 2. notifications/initialized
print("== initialized notification ==")
send({"jsonrpc": "2.0", "method": "notifications/initialized",
      "params": {}}, timeout=5)

# 3. tools/list
print("== tools/list ==")
r = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
tools = [t["name"] for t in r.get("result", {}).get("tools", [])]
print("  工具数:", len(tools))
print("  list_api_endpoints 在名单中:", "list_api_endpoints" in tools)
print("  全部工具:", tools)

# 4. tools/call list_api_endpoints
print("== tools/call list_api_endpoints ==")
r = send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "list_api_endpoints", "arguments": {}}})
result = r.get("result", {})
content = result.get("content", [])
text = "".join(c.get("text", "") for c in content) if isinstance(content, list) else str(content)
print("  isError:", result.get("isError"))
print("  返回内容长度:", len(text))
print("  内容前 300 字符:", text[:300])

proc.terminate()
