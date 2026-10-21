"""Versioned, design-only attack templates. No assets or adoption transactions."""
import copy
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


class TemplateConflict(ValueError):
    def __init__(self, path, sha):
        super().__init__("同名模板已存在，是否覆盖？")
        self.path, self.sha = str(path), sha


def filename(name):
    if not isinstance(name, str) or not name.strip() or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError("模板名称需为1～120个可见字符")
    name = name.strip()
    encoded = quote(name, safe="")
    if len(encoded) > 180:
        encoded = encoded[:140] + "~" + hashlib.sha256(name.encode()).hexdigest()[:24]
    return "t-" + encoded + ".json"


class TemplateStore:
    def __init__(self, root, validate):
        self.root = Path(root).resolve()
        self.folder = self.root / ".attack-templaates"
        self.validate = validate

    def path(self, name):
        path = self.folder / filename(name)
        if self.folder.resolve() != self.folder or path.is_symlink():
            raise ValueError("模板目录或文件不能指向项目以外的位置")
        return path

    def read(self, name):
        data = json.loads(self.path(name).read_text(encoding="utf-8"))
        if data.get("format") != "pvzhe.attack-template" or data.get("schemaVersion") != 1:
            raise ValueError("模板格式或版本不受支持")
        if data.get("name") != name.strip():
            raise ValueError("模板名称与文件不匹配")
        self.validate(data["design"])
        return data

    def catalog(self):
        if not self.folder.exists():
            return []
        if self.folder.resolve() != self.folder:
            raise ValueError("模板目录不能是外部链接")
        items = []
        for path in self.folder.glob("t-*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if path.name != filename(data["name"]):
                    continue
                self.read(data["name"])
                items.append(dict(name=data["name"]))
            except (ValueError, KeyError, OSError):
                continue
        return sorted(items, key=lambda item: item["name"].casefold())

    def write(self, name, design, reference, expected_sha=None):
        self.validate(design)
        path = self.path(name)
        old = None
        if path.exists():
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if expected_sha != sha:
                raise TemplateConflict(path, sha)
            old = self.read(name)
        elif expected_sha is not None:
            raise ValueError("原模板已移除，请重新保存")
        now = datetime.now(timezone.utc).isoformat()
        data = dict(format="pvzhe.attack-template", schemaVersion=1, name=name.strip(),
                    id=old["id"] if old else uuid.uuid4().hex,
                    createdAt=old["createdAt"] if old else now, updatedAt=now,
                    reference=reference, design=copy.deepcopy(design),
                    extensions=copy.deepcopy(old.get("extensions", {})) if old else {})
        self.folder.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if old:
            temp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
            try:
                temp.write_text(payload, encoding="utf-8")
                os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
        else:
            try:
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(payload)
            except FileExistsError:
                raise TemplateConflict(path, hashlib.sha256(path.read_bytes()).hexdigest())
        return dict(path=str(path), name=data["name"])
