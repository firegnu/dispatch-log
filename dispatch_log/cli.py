import argparse
import json
from pathlib import Path
import sys

from . import corral
from .record import Recorder
from .store import Store


def parser():
    root = argparse.ArgumentParser(description="显式、本地的任务过程记录器；不启动后台服务")
    root.add_argument("--data-dir", default="~/.local/share/dispatch-log")
    sub = root.add_subparsers(dest="action", required=True)
    new = sub.add_parser("new", help="声明项目/任务，创建派发 ID")
    new.add_argument("--project", required=True)
    new.add_argument("--task", required=True)
    new.add_argument("--parent")
    new.add_argument("--kind", choices=["initial", "review", "redispatch"], default="initial")
    listing = sub.add_parser("ls", help="列出已记录的派发")
    listing.add_argument("--project")
    listing.add_argument("--task")
    sub.add_parser("show", help="读取派发及事件 JSON").add_argument("dispatch")
    sub.add_parser("cat", help="按哈希读取原文").add_argument("sha256")
    decision = sub.add_parser("decide", help="记录主控实际选择与理由")
    decision.add_argument("--dispatch", required=True)
    for name in ["model", "effort", "budget", "reason"]:
        decision.add_argument("--" + name, required=True)
    note = sub.add_parser("note", help="记录主控审查/返工；默认从 stdin 读原文")
    note.add_argument("--dispatch", required=True)
    note.add_argument("--kind", choices=["review", "rework", "decision"], required=True)
    note.add_argument("--file")
    for action in ["start", "send", "reply"]:
        wrapper = sub.add_parser(action, help=f"执行一次 corral {action} 并记录")
        wrapper.add_argument("--dispatch")
        if action in {"start", "send"}:
            wrapper.add_argument("--task-file")
        if action == "send":
            wrapper.add_argument("--kind", choices=["followup", "rework"], default="followup")
        wrapper.add_argument("command", nargs=argparse.REMAINDER)
    route = sub.add_parser("route", help="从 stdin 读摘要；方案 B，版本不符在请求前降级 A")
    route.add_argument("--dispatch")
    route.add_argument("--route-file", default="~/.agents/skills/corral-dispatch/route.py")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    store = Store(args.data_dir)
    try:
        if args.action == "new":
            print(store.create(args.project, args.task, args.kind, args.parent)["dispatch_id"])
        elif args.action == "ls":
            print(json.dumps(store.list(args.project, args.task), ensure_ascii=False, indent=2))
        elif args.action == "show":
            print(json.dumps({"dispatch": store.get(args.dispatch), "events": store.events(args.dispatch)},
                             ensure_ascii=False, indent=2))
        elif args.action == "cat":
            sys.stdout.buffer.write(store.read_blob(args.sha256))
        elif args.action in {"decide", "note"}:
            context = store.get(args.dispatch)
            if args.action == "decide":
                data = {key: getattr(args, key) for key in ["model", "effort", "budget", "reason"]}
            else:
                content = Path(args.file).read_bytes() if args.file else sys.stdin.buffer.read()
                data = {"kind": args.kind, "content": store.blob(content)}
            store.event(args.dispatch, context, "controller." + args.action, data, "controller_statement")
        elif args.action == "route":
            from .route import execute
            return execute(Path(args.route_file).expanduser(), sys.stdin.read(),
                           Recorder(store, args.dispatch))
        else:
            return corral.execute(args.action, args.command, Recorder(store, args.dispatch),
                                  getattr(args, "task_file", None), getattr(args, "kind", "followup"))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"dlog: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
