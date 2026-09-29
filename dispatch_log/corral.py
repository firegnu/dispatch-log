"""Wrap only explicit start/send/reply commands; never infer task membership."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from .store import now


def option_values(tokens, names):
    values = []
    for index, token in enumerate(tokens):
        if token in names and index + 1 < len(tokens):
            values.append(tokens[index + 1])
        elif any(token.startswith(name + "=") for name in names):
            values.append(token.split("=", 1)[1])
    return values


def last_option(tokens, names, default=None):
    values = option_values(tokens, names)
    return values[-1] if values else default


def send_positionals(tokens):
    """Mirror `corral send --help`; any other option makes name/text unknown (None)."""
    positionals, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return positionals + tokens[index + 1:]
        if token.partition("=")[0] in {"--after", "--timeout"}:
            index += 1 if "=" in token else 2
            continue
        if token.startswith("-") and token != "--force":
            return None
        if token != "--force":
            positionals.append(token)
        index += 1
    return positionals


def snapshot(task_file, cwd, recorder):
    path = Path(task_file).expanduser()
    path = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
    content = recorder.attempt("task_file", path.read_bytes)
    return {"path": str(path), "read_at": now(),
            "content": recorder.blob(content) if content is not None else None}


def start_data(command, task_file, recorder):
    tokens = command[2:]
    split = tokens.index("--") if "--" in tokens else len(tokens)
    options, agent = tokens[:split], tokens[split + 1:]
    cwd = Path(last_option(options, ["--cwd"], os.getcwd())).expanduser().resolve()
    labels = {}
    for label in option_values(options, ["--label"]):
        key, separator, value = label.partition("=")
        if separator and key in {"model", "effort", "role"}:
            labels[key] = value
    # Labels are declarations; these are selected arguments of the actual invocation.
    parameters = {"model": last_option(agent, ["--model", "-m"]),
                  "effort": last_option(agent, ["--effort"])}
    for config in option_values(agent, ["-c", "--config"]):
        key, separator, value = config.partition("=")
        if separator and key in {"model", "model_reasoning_effort"}:
            parameters["model" if key == "model" else "effort"] = value.strip('"\'')
    prompt = last_option(options, ["--prompt"])
    data = {"cwd": str(cwd), "labels": labels, "agent_parameters": parameters,
            "agent_program": Path(agent[0]).name if agent else None,
            "prompt": recorder.blob(prompt) if prompt is not None else None,
            "task_file": None, "snapshot_semantics": "file_before_invocation_not_proof_of_read"}
    if task_file:
        data["task_file"] = snapshot(task_file, cwd, recorder)
    return data


def execute(action, command, recorder, task_file=None, kind="followup"):
    if command and command[0] == "--":
        command = command[1:]
    if len(command) < 3 or command[1] != action:
        raise ValueError(f"需要显式命令：-- corral {action} ...（尚未执行）")
    operation_id = uuid.uuid4().hex
    if action == "start":
        data = start_data(command, task_file, recorder)
    elif action == "reply":
        data = {"target_name": command[2]}
    else:
        positionals = send_positionals(command[2:])
        if positionals is not None and len(positionals) < 2:
            raise ValueError("send 缺少名字或文本（尚未执行）")
        data = {"target_name": None, "text": None, "kind": kind}
        if positionals is None or len(positionals) > 2:
            data["missing_reason"] = "unrecognized_send_arguments"
        else:
            data.update({"target_name": positionals[0], "text": recorder.blob(positionals[1])})
        if task_file:
            data["task_file"] = snapshot(task_file, Path.cwd(), recorder)
            data["snapshot_semantics"] = "file_before_invocation_not_proof_of_read"
    data.update({"operation_id": operation_id, "requested_at": now()})
    # An intent without a result means completion is UNKNOWN, not failed/not run.
    recorder.event("corral.intent", {"action": action, **data})
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE)
    except OSError as error:
        recorder.event(f"corral.{action}", {**data, "execution": "not_started",
                                           "error_type": type(error).__name__})
        print("dlog: 无法启动命令；未重试。", file=sys.stderr)
        return 127
    sys.stdout.buffer.write(result.stdout)
    sys.stdout.buffer.flush()
    try:
        response = json.loads(result.stdout)
        if not isinstance(response, dict):
            raise ValueError("not an object")
    except (ValueError, UnicodeError):
        response = {}
        data["response_status"] = "unparseable"
    allowed = ("ok", "name", "instance", "confirmed", "merged_with_draft",
               "pending", "after", "after_instance", "at", "error")
    # Do not persist arbitrary response errors/messages or nested values.
    observed = {key: response[key] for key in allowed if key in response
                and isinstance(response[key], (str, bool, int, float, type(None)))}
    observed.pop("error", None)
    data.update({"result": observed, "exit_code": result.returncode, "completed_at": now()})
    if action == "send":
        data["delivery"] = ("queued" if response.get("pending") is True else
                            "confirmed" if response.get("confirmed") is True else "unconfirmed")
        data["complete_input_known"] = (response.get("confirmed") is True
                                         and response.get("merged_with_draft") is False)
    if action == "reply":
        text = response.get("text")
        data["reply"] = recorder.blob(text) if isinstance(text, str) else None
        history = (recorder.attempt("instance_check", lambda: recorder.store.events(recorder.dispatch))
                   if recorder.dispatch and recorder.context else [])
        instances = {event["data"].get("result", {}).get("instance") for event in (history or [])
                     if event["kind"] in {"corral.start", "corral.send"}}
        instances.discard(None)
        current = response.get("instance")
        data["instance_check"] = ("unknown" if not current or not instances else
                                  "consistent" if instances == {current} else "mismatch")
        data["causal_link"] = "not_proven"
    recorder.event(f"corral.{action}", data)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode
