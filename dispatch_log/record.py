"""Best-effort recording must never turn a completed operation into a retry."""
import sys


class Recorder:
    def __init__(self, store, dispatch):
        self.store = store
        self.dispatch = dispatch
        self.context = {}
        self.gaps = []
        if dispatch:
            self.context = self.attempt("dispatch_context", lambda: store.get(dispatch)) or {}

    def attempt(self, stage, action):
        try:
            return action()
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.gaps.append({"stage": stage, "error_type": type(error).__name__})
            # Do not echo arbitrary exception messages, argv or response contents.
            print(f"dlog: 记录失败 ({stage}, {type(error).__name__})；"
                  "真实操作结果以其 stdout/退出码为准，不要因记录失败重发。", file=sys.stderr)
            return None

    def blob(self, value):
        return self.attempt("blob", lambda: self.store.blob(value))

    def event(self, kind, data, source="recorder_observation"):
        return self.attempt("event", lambda: self.store.event(
            self.dispatch, self.context, kind, {**data, "recording_gaps": list(self.gaps)}, source))
