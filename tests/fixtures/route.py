"""Synthetic route protocol fixture, never a network client."""
import os


def build_request(summary):
    return {"model": "synthetic", "state": {"task_summary": summary}}


def call(payload, key):
    marker = os.environ.get("DLOG_TEST_CALLS")
    if marker:
        with open(marker, "a") as handle:
            handle.write("call\n")
    if os.environ.get("DLOG_TEST_FAIL"):
        raise RuntimeError("synthetic failure")
    return {"score": 0.123456789, "extra": "kept before shape", "model": "synthetic"}


def shape(response):
    return {"ok": True, "score": round(response["score"], 3)}


def route(summary, key=None):
    key = key or os.environ.get("TYPESAFE_API_KEY")
    if not key:
        return {"ok": False, "error": "TYPESAFE_API_KEY is not set"}
    try:
        return shape(call(build_request(summary), key))
    except Exception as error:
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


if __name__ == "__main__":
    import json
    import sys
    result = route(sys.stdin.read().strip())
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)
