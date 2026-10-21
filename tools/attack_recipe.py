"""Validate, export and bind confirmed web-editor recipes. Never run or install a Mod."""
import argparse
import copy
import json
from pathlib import Path
import uuid

from attack_model import digest, file_sha, load_session, save
from attack_plan import bind_implementation, design_digest, same_design, implementation_changes, load_plan, store_plan
from attack_web import ORIGIN_PRESETS, compile_recipe, load_recipe


def check_release(config, root):
    """Verify actual PCK/DLL inputs, not just a previous cache manifest or mtime."""
    from game_cache import GameCache
    work = Path(root).resolve() / ".work"
    release = json.loads((work / "release.json").read_text(encoding="utf-8"))
    cache = GameCache(work, release)
    provenance = config.get("provenance", {})
    if provenance.get("releaseCacheKey") != cache.key or digest(provenance.get("release")) != digest(cache.identity):
        raise ValueError("素材会话与当前发行基线不同，不能沿用；请重新准备匹配素材")
    if cache.identity["assemblies"].get("PlantsVsZombies.dll") != ORIGIN_PRESETS["dllSha256"]:
        raise ValueError("出弹位置预设需要按当前发行重新核对")
    if not {"background", "plant", "target"}.issubset(config["assets"]):
        raise ValueError("缺少草坪、植物或目标透明素材")


def new_session(source, output, root, action=None):
    output = Path(output)
    if output.exists():
        raise ValueError("新会话路径已存在")
    config = load_session(source)
    if config["schemaVersion"] != 3:
        raise ValueError("请先用当前准备器生成素材会话")
    check_release(config, root)
    config["sessionId"] = uuid.uuid4().hex
    if action:
        config.setdefault("binding", {})["action"] = action
    save(output, config)
    return dict(sessionId=config["sessionId"], sessionPath=str(output.resolve()))


def verify_result(result_path, session_path, server_path, recipe_path, plan_path, root):
    root = Path(root).resolve()
    recipe_path, plan_path = Path(recipe_path).resolve(), Path(plan_path).resolve()
    if recipe_path == plan_path:
        raise ValueError("recipe与编译方案不能使用同一路径")
    config = load_session(session_path)
    check_release(config, root)
    record = json.loads(Path(result_path).read_text(encoding="utf-8"))
    server = json.loads(Path(server_path).read_text(encoding="utf-8"))
    if record.get("format") != "pvzhe.attack-recipe-result" or record.get("schemaVersion") != 2:
        raise ValueError("不支持的网页反馈格式")
    if record.get("status") != "confirmed" or record.get("demo") is not False or record.get("viewOnly") is not False:
        raise ValueError("只有真实素材编辑会话的confirmed结果可采用；草稿、查看、演示和取消均不可采用")
    if server.get("demo") is not False or server.get("viewOnly") is not False:
        raise ValueError("服务会话不是正式编辑模式")
    if not record.get("transactionId") or record["transactionId"] != server.get("transactionId"):
        raise ValueError("反馈不属于本轮服务")
    for obj in (record, server):
        if obj.get("sessionId") != config["sessionId"] or obj.get("configSha256") != digest(config):
            raise ValueError("会话/素材配置身份不匹配")
    if server.get("recipePath") != str(recipe_path) or server.get("planPath") != str(plan_path):
        raise ValueError("输出方案与启动时指定的项目路径不匹配")
    if record.get("assets") != config["assets"] or record.get("provenance") != config.get("provenance", {}) or record.get("binding") != config.get("binding", {}):
        raise ValueError("素材来源或目标动作发生变化")
    if record.get("originPresetCatalogSha256") != digest(ORIGIN_PRESETS):
        raise ValueError("预设资料已经改变，需要重新确认")
    recipe, _ = load_recipe(recipe_path)
    if recipe["character"] != config["plant"]["key"] or record.get("recipe") != recipe or record.get("recipeSha256") != digest(recipe):
        raise ValueError("确认后的正式recipe已变或角色不匹配")
    compiled = compile_recipe(recipe)
    if record.get("plan") != compiled or record.get("planSha256") != digest(compiled):
        raise ValueError("编译方案与确认参数不一致")
    current_sha = file_sha(plan_path) if plan_path.exists() else None
    if current_sha != record.get("sourcePlanSha256"):
        raise ValueError("已有编排在确认后已变，不能覆盖；已导出的结果也不能重复覆盖")
    if current_sha:
        existing = load_plan(plan_path)
        if implementation_changes(existing, root):
            raise ValueError("实现文件已变，先调查设计漂移")
        compiled["implementation"] = copy.deepcopy(existing["implementation"])
    compiled["reference"] = dict(releaseCacheKey=config["provenance"]["releaseCacheKey"],
                                 recipeSha256=digest(recipe), originPresetCatalogSha256=digest(ORIGIN_PRESETS))
    return compiled


def export_result(result, session, server, recipe, plan, root):
    compiled = verify_result(result, session, server, recipe, plan, root)
    store_plan(plan, compiled)
    return dict(status="exported", planPath=str(Path(plan).resolve()), implementationPending=True)


def bind_recipe(recipe, plan, files, root):
    r, _ = load_recipe(recipe)
    p = load_plan(plan)
    if not same_design(p,compile_recipe(r)) or p.get("reference", {}).get("recipeSha256") != digest(r):
        raise ValueError("recipe与落地方案不同，不能登记实现")
    if not files:
        raise ValueError("至少指定一个实际实现文件")
    store_plan(plan, bind_implementation(p, files, root))
    return dict(status="bound", planPath=str(Path(plan).resolve()), note="仅登记文件摘要；本命令不执行游戏验收")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("new-session")
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--action")
    for name in ("check", "export"):
        p = sub.add_parser(name)
        for key in ("result", "session", "server", "recipe", "plan"):
            p.add_argument("--" + key, required=True)
    bind = sub.add_parser("bind")
    bind.add_argument("--recipe", required=True)
    bind.add_argument("--plan", required=True)
    bind.add_argument("--file", action="append", required=True)
    for p in (prepare, *[sub.choices[k] for k in ("check", "export")], bind):
        p.add_argument("--root", default=str(Path.cwd()))
    args = parser.parse_args()
    try:
        if args.command == "new-session":
            result = new_session(args.source, args.output, args.root, args.action)
        elif args.command == "bind":
            result = bind_recipe(args.recipe, args.plan, args.file, args.root)
        else:
            values = (args.result, args.session, args.server, args.recipe, args.plan, args.root)
            if args.command == "check":
                verify_result(*values)
                result = dict(status="valid", appliesMod=False)
            else:
                result = export_result(*values)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
