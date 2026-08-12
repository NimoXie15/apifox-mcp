# -*- coding: utf-8 -*-
"""apifox_mcp 改造脚本：加模块 ID 支持 + 全部 export_payload 替换为 _build_export_payload()"""
import pathlib

BASE = pathlib.Path(r"D:\files\apifox-mcp\src")


def replace_payload_blocks(text: str) -> tuple[str, int]:
    """按花括号配对替换 export_payload = {...} 块，返回新文本与替换次数"""
    lines = text.split("\n")
    out = []
    i = 0
    replaced = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("export_payload = {") and not stripped.startswith("export_payload = _build"):
            depth = 0
            j = i
            while j < len(lines):
                for ch in lines[j]:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                j += 1
                if depth == 0:
                    break
            indent = line[: len(line) - len(line.lstrip())]
            out.append(indent + "export_payload = _build_export_payload()")
            replaced += 1
            i = j
        else:
            out.append(line)
            i += 1
    return "\n".join(out), replaced


def add_import(text: str, name: str) -> tuple[str, bool]:
    """在 from ..utils import ... 中补入 name（字典序），返回新文本与是否改动"""
    lines = text.split("\n")
    changed = False
    for idx, line in enumerate(lines):
        if line.startswith("from ..utils import"):
            if name in line:
                return text, False
            names = line.split("import", 1)[1].strip().split(",")
            names = [n.strip() for n in names if n.strip()]
            names.append(name)
            # 字典序排序，保持原风格（无括号单行）
            names.sort()
            lines[idx] = "from ..utils import " + ", ".join(names)
            changed = True
            break
    return "\n".join(lines), changed


# ---------- 1. config.py ----------
cfg = BASE / "config.py"
text = cfg.read_text(encoding="utf-8")
if "APIFOX_MODULE_ID" not in text:
    marker = 'APIFOX_BASE_URL = os.getenv("APIFOX_BASE_URL")'
    assert marker in text, "config.py 未找到 APIFOX_BASE_URL 行"
    text = text.replace(
        marker,
        marker + '\nAPIFOX_MODULE_ID = os.getenv("APIFOX_MODULE_ID")  # 可选，指定模块 ID 实现按模块动态读取',
        1,
    )
    cfg.write_text(text, encoding="utf-8")
    print("[config.py] +APIFOX_MODULE_ID")
else:
    print("[config.py] APIFOX_MODULE_ID 已存在，跳过")

# ---------- 2. utils.py ----------
utils = BASE / "utils.py"
text = utils.read_text(encoding="utf-8")
# 2.1 import 加 APIFOX_MODULE_ID
if "APIFOX_MODULE_ID" not in text.split("def _build_export_payload", 1)[0].split("def _validate_config", 1)[0] if "def _build_export_payload" in text else text:
    if "APIFOX_MODULE_ID" not in text:
        imp_lines = text.split("\n")
        for idx, line in enumerate(imp_lines):
            if "from .config import" in line:
                # 该 import 是多行括号形式
                end = idx
                while ")" not in imp_lines[end]:
                    end += 1
                block = imp_lines[idx : end + 1]
                # 找到最后一个名字行，在其后追加
                joined = "\n".join(block)
                assert "PROJECT_ID" in joined
                new_block = joined.replace(
                    "APIFOX_API_VERSION, HTTP_STATUS_CODES, logger",
                    "APIFOX_API_VERSION, APIFOX_MODULE_ID, HTTP_STATUS_CODES, logger",
                    1,
                )
                if new_block == joined:
                    raise SystemExit("utils.py import 追加失败")
                imp_lines = imp_lines[:idx] + [new_block] + imp_lines[end + 1 :]
                text = "\n".join(imp_lines)
                utils.write_text(text, encoding="utf-8")
                print("[utils.py] import +APIFOX_MODULE_ID")
                break
        else:
            raise SystemExit("utils.py 未找到 from .config import")
    else:
        print("[utils.py] APIFOX_MODULE_ID 已存在")
else:
    print("[utils.py] APIFOX_MODULE_ID 已存在")

# 2.2 插入 _build_export_payload 函数（在 _validate_config 之前）
text = utils.read_text(encoding="utf-8")
if "def _build_export_payload" not in text:
    func = '''def _build_export_payload(scope_type: str = "ALL") -> Dict[str, Any]:
    """
    构建导出 OpenAPI 的请求体。配置了 APIFOX_MODULE_ID 时自动带上 moduleId，实现按模块动态导出。
    """
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


'''
    marker = "def _validate_config() -> Optional[str]:"
    assert marker in text, "utils.py 未找到 _validate_config"
    text = text.replace(marker, func + marker, 1)
    utils.write_text(text, encoding="utf-8")
    print("[utils.py] +_build_export_payload()")
else:
    print("[utils.py] _build_export_payload 已存在")

# ---------- 3. tools/*.py ----------
expect = {
    "api_tools.py": 3,
    "audit_tools.py": 2,
    "config_tools.py": 1,
    "folder_tools.py": 1,
    "schema_tools.py": 2,
    "tag_tools.py": 3,
    "validation_tools.py": 2,
    "crud_tools.py": 0,
}
for fname, expected in expect.items():
    fp = BASE / "tools" / fname
    text = fp.read_text(encoding="utf-8")
    new_text, count = replace_payload_blocks(text)
    if count != expected:
        print(f"[{fname}] !! 替换数 {count} != 期望 {expected}")
    else:
        print(f"[{fname}] 替换 {count} 处")
    new_text, imp_changed = add_import(new_text, "_build_export_payload")
    if imp_changed:
        print(f"[{fname}] import +_build_export_payload")
    fp.write_text(new_text, encoding="utf-8")

print("\n改造完成")
