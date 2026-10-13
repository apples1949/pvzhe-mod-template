"""Template metadata policy; intentionally independent of host API permissiveness."""
import re

MOD_ID = re.compile(r"[0-9a-z_.-]{1,32}")
SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
EXAMPLE_IDS = {"local.hello-world", "local.feature-lab"}
PLACEHOLDERS = {
    "name": {"Hello World 模板", "功能开发示例", "Your Mod Name", "TODO"},
    "author": {"Mod 开发者", "Mod开发者", "Your Name", "YourName", "TODO", "待填写"},
}


def validate_metadata(manifest, release=False):
    if not isinstance(manifest, dict):
        raise ValueError("mod.json must contain an object")
    for key in ("id", "name", "author", "version"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key}: required non-empty string")
        if value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f"{key}: whitespace at edges/control characters are not allowed")
    if not MOD_ID.fullmatch(manifest["id"]) or manifest["id"] in (".", ".."):
        raise ValueError("id: use 1..32 lowercase ASCII letters, digits, _, - or .; no slashes")
    # UTF-16 units match common C# string length semantics; supplementary symbols use two.
    try:
        author_length = len(manifest["author"].encode("utf-16-le")) // 2
    except UnicodeEncodeError as error:
        raise ValueError("author: invalid Unicode") from error
    if author_length > 32:
        raise ValueError("author: maximum 32 UTF-16 units")
    version = manifest["version"]
    match = SEMVER.fullmatch(version)
    if len(version) > 32 or not match or (
        match.group(4) and any(x.isascii() and x.isdigit() and len(x) > 1 and x[0] == "0"
                               for x in match.group(4).split("."))
    ):
        raise ValueError("version: maximum 32 characters, valid SemVer required (e.g. 0.1.0)")
    if release:
        if manifest["id"] in EXAMPLE_IDS:
            raise ValueError("id: replace the template/example ID before release")
        for key, values in PLACEHOLDERS.items():
            if manifest[key].casefold() in {v.casefold() for v in values}:
                raise ValueError(f"{key}: replace placeholder and confirm with the user before release")
