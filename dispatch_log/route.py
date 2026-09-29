"""Version-pinned adapter; no change to the installed routing script."""
import hashlib
import json
import os
import subprocess
import sys
import types
import uuid

from .store import encoded


TRUSTED_SHA256 = {"d4ab1cc82fe5c1b10987800eaf1c44d1e1fe026e7b1227b0eeb508cce548167a"}


def load_module(path, source):
    module = types.ModuleType("_dispatch_log_route")
    module.__file__ = str(path)
    # Execute the exact bytes we hashed, without writing upstream __pycache__.
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def fallback(path, summary, recorder, data):
    print("dlog: route.py 版本未适配，请求前降级为 A；完整解析响应未记录。", file=sys.stderr)
    data.update({"mode": "A", "parsed_response": None,
                 "missing_reason": "unverified_route_version"})
    recorder.event("jev.intent", data)
    # Only this path executes the script; never entered after a B request.
    result = subprocess.run([sys.executable, str(path)], input=summary.encode(), stdout=subprocess.PIPE)
    sys.stdout.buffer.write(result.stdout)
    sys.stdout.buffer.flush()
    try:
        parsed = json.loads(result.stdout)
        public = {key: parsed[key] for key in ("ok", "model", "tier", "cross_review", "impact", "usage")
                  if key in parsed} if isinstance(parsed, dict) else None
    except (ValueError, UnicodeError):
        public = None
    data.update({"exit_code": result.returncode,
                 "suggestion": recorder.blob(encoded(public)) if public is not None else None})
    recorder.event("jev.route", data)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


def execute(path, summary, recorder):
    path = path.resolve()
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    data = {"operation_id": uuid.uuid4().hex, "route_path": str(path), "route_sha256": digest,
            "summary": recorder.blob(summary), "mode": "B", "request": None,
            "parsed_response": None, "response_semantics": "parsed_json_not_http_bytes"}
    if digest not in TRUSTED_SHA256:
        return fallback(path, summary, recorder, data)
    module = load_module(path, source)
    # Only versions reviewed to expose these functions enter B.
    for name in ("build_request", "call", "shape"):
        if not callable(getattr(module, name, None)):
            return fallback(path, summary, recorder, data)
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        result = {"ok": False, "error": "TYPESAFE_API_KEY is not set"}
        data["error_type"] = "missing_key"
    else:
        try:
            payload = module.build_request(summary.strip())
            data["request"] = recorder.blob(encoded(payload))
            recorder.event("jev.intent", data)
            # Authentication is used only by the existing request function, never recorded.
            response = module.call(payload, key)
            data["parsed_response"] = recorder.blob(encoded(response))
            result = module.shape(response)
        except Exception as error:
            # No fallback/replay here: the request may already have reached JEV.
            result = {"ok": False, "error": f"{type(error).__name__}: {error}"}
            data["error_type"] = type(error).__name__
    code = 0 if result["ok"] else 1
    print(json.dumps(result, ensure_ascii=False))
    # Success contains the public suggestion; errors are not persisted as arbitrary text.
    data.update({"exit_code": code,
                 "suggestion": recorder.blob(encoded(result)) if result["ok"] else None})
    recorder.event("jev.route", data)
    return code
