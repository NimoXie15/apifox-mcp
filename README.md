# Apifox MCP 服务器（改造版 · 支持按模块动态读取）

> 让 AI 助手通过 MCP 协议管理 Apifox 项目的接口文档：创建/更新/审计 API、管理数据模型、检查命名与响应一致性。
> 本仓库是 [iwen-conf/apifox-mcp](https://github.com/iwen-conf/apifox-mcp) 的**改造版**：
> 原版 Python MCP 包不支持按模块读取，本版新增 `APIFOX_MODULE_ID` 支持（按模块动态导出/导入），并修复了导入写操作落错模块的问题。
>
> ⚠️ **安全**：凡涉及 API Token 处均为占位符，真实 Token 只存在于本机 `.zcode/config.json` 的环境变量中，**严禁写入任何将要上传 git 的文件**。

---

## 目录结构

```
apifox-mcp/
├── src/                      # 改造后的运行包（包名 src，唯一可改的源码）
│   ├── config.py  utils.py  main.py  __init__.py
│   └── tools/               # 9 个 MCP 工具文件
├── requirements.txt         # 依赖（锁定 mcp[cli]==1.29.0）
├── README.md                # 本文件
├── modify.py                # 上游→改造版的自动改造脚本
├── send_mcp.py              # JSON-RPC 验证脚本（token 从环境变量读取）
├── venv/                    # 虚拟环境（.gitignore 已忽略，不上传）
└── src/*.old                 # 上游原版文件对照（.gitignore 已忽略，仅本地参考）
```

> `.old` 后缀文件是上游原版（`config.py.old`、`utils.py.old`、`tools/*.old` 等），
> 与改造版同目录存放，便于 diff 对照；它们不会被 Python 加载，也不会上传 git。

---

## 快速开始

### 1. 安装依赖（必须锁定 mcp 1.x）

```bash
python -m venv venv
venv/Scripts/pip install -r requirements.txt   # Windows
venv/bin/pip install -r requirements.txt       # Linux/macOS
```

- **不能装 mcp 2.x**——它移除了 FastMCP API，本包会启动失败。
- Python ≥ 3.10（mcp 1.x 要求）。
- ⚠️ Windows 下系统 PATH 里的 `python` 可能是 Microsoft Store 占位符（WindowsApps），**不可用**，务必用 venv 内的解释器。

### 2. 配置环境变量（四件套）

| 变量 | 说明 |
|---|---|
| `APIFOX_TOKEN` | Apifox 开放 API Token（登录 Apifox 后获取） |
| `APIFOX_PROJECT_ID` | 项目 ID |
| `APIFOX_MODULE_ID` | 目标模块 ID（配置后按模块动态读取/写入） |
| `PYTHONPATH` | 指向本仓库根目录绝对路径（如 `D:\files\apifox-mcp`） |

### 3. 注册 MCP 服务器

服务器名 = **探测出的模块名 + " API 文档"**（如"管理侧接口 API 文档"）。

**探测模块名**：调一次导出接口，响应 `info.title` 即模块名：

```
POST https://api.apifox.com/v1/projects/{项目ID}/export-openapi?locale=zh-CN
Header: Authorization: Bearer {Token}  +  X-Apifox-Api-Version: 2024-03-28
Body: {"scope":{"type":"ALL"},"oasVersion":"3.1","exportFormat":"JSON","moduleId":{模块ID}}
```

**注册方式**（命令指向 venv python，args `["-m","src.main"]`）：

- Claude Code：`claude mcp add <名称> -- <venv python> -m src.main`（用 `--env` 传四件套）
- Codex / Gemini CLI：`codex mcp add ...` / `gemini mcp add ...`
- Cursor / Windsurf / WorkBuddy：写入对应 `mcp.json` / `mcp_config.json`（`mcpServers` 条目）
- 项目下 `.mcp.json`：合并写入
- **zcode（本机客户端）**：写 workspace 级 `<repo>/.zcode/config.json`：

```json
{
  "mcp": {
    "servers": {
      "管理侧接口 API 文档": {
        "command": "<venv python 绝对路径>",
        "args": ["-m", "src.main"],
        "env": {
          "APIFOX_TOKEN": "<Token>",
          "APIFOX_PROJECT_ID": "<你的项目ID>",
          "APIFOX_MODULE_ID": "<你的模块ID>",
          "PYTHONPATH": "<仓库根目录绝对路径>"
        }
      }
    }
  }
}
```

zcode 对 workspace 级 MCP 默认信任并自动连接，**配置后需重启会话生效**。
⚠️ `.zcode/` 含明文 token，务必加入 `.gitignore`。

### 4. 验证

向 MCP 进程 stdin 发 JSON-RPC（或直接跑 `send_mcp.py`）：

1. `initialize`（protocolVersion `2024-11-05`）
2. `notifications/initialized`
3. `tools/list` → 应含 `list_api_endpoints` 等 22 个工具
4. `tools/call` 调 `list_api_endpoints` → 能返回接口列表

> ⚠️ Windows 下**不要用 select 读子进程 stdout**（用线程+队列）；手写测试脚本时子进程要**继承完整系统环境**
> （`env = dict(os.environ)` 再叠加），否则 Python 的 `_overlapped`（Winsock）加载失败报 `WinError 10106`。
> zcode 客户端本身会继承父进程环境，不受此影响。

---

## 改造记录（相对上游）

### 改动文件清单

| 文件 | 改动 |
|---|---|
| `config.py` | 新增 `APIFOX_MODULE_ID` 环境变量读取 |
| `utils.py` | 新增 `_build_export_payload()`；import 加 `APIFOX_MODULE_ID` |
| `tools/api_tools.py` | 硬编码 export_payload → 函数；create/update 的 import 加 `options.moduleId` |
| `tools/crud_tools.py` | export_payload → 函数；generate_crud 的 import 加 `options.moduleId` |
| `tools/audit_tools.py` 等 6 个 | 硬编码 export_payload → 函数 |
| `main.py` / `__init__.py` | 未改 |

### 核心改造点

**① 按模块动态读取（config.py）**

```python
APIFOX_MODULE_ID = os.getenv("APIFOX_MODULE_ID")  # 可选，指定模块 ID 实现按模块动态读取
```

**② 统一导出请求体（utils.py）**

```python
def _build_export_payload(scope_type: str = "ALL") -> Dict[str, Any]:
    """构建导出 OpenAPI 的请求体。配置了 APIFOX_MODULE_ID 时自动带上 moduleId，实现按模块动态导出。"""
    payload: Dict[str, Any] = {
        "scope": {"type": scope_type},
        "options": {"includeApifoxExtensionProperties": True, "addFoldersToTags": False},
        "oasVersion": "3.1",
        "exportFormat": "JSON"
    }
    if APIFOX_MODULE_ID:
        try:
            payload["moduleId"] = int(APIFOX_MODULE_ID)
        except ValueError:
            pass
    return payload
```

**③ 导入写操作带 moduleId（api_tools / crud_tools）**

```python
# 配置了 APIFOX_MODULE_ID 时导入到指定模块，否则保持原逻辑落到默认模块
if APIFOX_MODULE_ID:
    import_payload["options"]["moduleId"] = APIFOX_MODULE_ID
```

> ⚠️ `moduleId` **必须放在 `options` 对象内**——放在请求体顶层会被 Apifox 忽略，
> 接口会落进项目**默认模块**（默认模块与目标模块是两套独立实体，客户端看不到变化）。
> 这是曾污染默认模块的根因，务必遵守。

---

## 能力边界与踩坑记录

1. **导入不写 moduleId → 全落默认模块**：见上文改造点③，本仓库曾因此污染默认模块。
2. **参数名**：`targetEndpointFolderId` / `targetSchemaFolderId` 是正确参数名（与上游 Go CLI 一致），`endpointFolderId` 也能用，二者皆可。
3. **security（鉴权）写不进 token 值**：import 对 `security` 只做方案关联（`schemeGroups` 引用 `bearerAuth`），`authConfigs.token` 的**具体值写不进去**（合并保留旧值/置空）。token 值请在客户端用「继承」+ 环境变量（`{{bearerToken}}` / `{{refreshToken}}`）实现。注意：刷新 token 类接口用 `{{refreshToken}}`，其余用 `{{bearerToken}}`；登录类接口无需鉴权。
4. **删除受限（平台限制，非 bug）**：官方文档明示 `delete endpoint / delete schema / create+delete folder` 均不支持——公开 API 与内部 API 均无删除端点（`DELETE /modules/{id}` 端点存在但返回 403）。数据模型/目录只能在客户端手动删。
5. **客户端看到旧数据**：MCP 摘要/详情接口导出时带 `moduleId`，Apifox 服务端对该参数组合有**导出缓存**；不带 moduleId 的导出是准的。客户端刷新（Cmd/Ctrl+R）可强制更新。
6. **数据模型 id 分段**：目标模块与默认模块的数据模型 id 段不同，清理时认 id 段，别误删。

### 上游能力边界（源自上游 README / AGENTS / SKILL）

- 上游官方主推 **Go CLI**（`cmd/apifox-cli`），Python MCP 包为 legacy 兼容层；本仓库专注 Python 版。
- 上游 `import-openapi` 的 options 参数名：`targetEndpointFolderId` / `targetSchemaFolderId`。

---

## 收尾自查清单

- [ ] 服务器名（探测出的模块名 + " API 文档"）
- [ ] 配置写入位置（哪个工具/文件）与是否需重启/信任
- [ ] 导入类工具带 `options.moduleId`
- [ ] 仓库无明文 token（`grep -r "afxp_" .` 应无命中）

---

## License

MIT（上游同源）。
