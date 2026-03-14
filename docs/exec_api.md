# `Codex` API

`Codex` is the simplest way to drive Codex from Python. It uses a private local stdio
app-server session under the hood and exposes a small thread-oriented API for
request/response and streamed runs.

Use `from codex import ...` for this high-level facade. If you need the raw app-server client,
import that separately from `codex.app_server`.

## Happy path

```python
from codex import Codex

client = Codex()
stream = client.run("Diagnose the failing tests and propose a fix")
stream.wait()
print(stream.final_text)
print(stream.items)
print(stream.usage)
```

`Codex.run*()` starts a fresh internal thread for that call. If you want to keep context across
multiple runs, create or resume a `Thread` explicitly. The underlying private app-server session
is reused for the lifetime of the `Codex` instance.

## Streaming

Use `run()` when you want access to the typed app-server notification stream:

```python
from codex import Codex
from codex.protocol import types as protocol

client = Codex()
stream = client.run("Investigate the flaky test")
for event in stream:
    if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
        print(event.params.delta, end="", flush=True)
```

## Structured output

```python
from pydantic import BaseModel

from codex import Codex, TurnOptions


class Summary(BaseModel):
    answer: str

schema = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}

client = Codex()
payload = client.run_json("Return JSON matching the schema", TurnOptions(output_schema=schema))
payload_from_model = client.run_json(
    "Return JSON matching the schema",
    TurnOptions(output_schema=Summary),
)
print(payload["answer"])
```

If you want typed validation directly, use `client.run_model("Return JSON matching the schema", Summary)`.

## Inputs

`Thread.run()` accepts either:

- a plain string
- a list of protocol-native text and local-image input items

Example:

```python
from codex import Codex

client = Codex()
result = client.run(
    [
        {"type": "text", "text": "Describe these screenshots"},
        {"type": "localImage", "path": "./ui.png"},
    ]
)
```

## Resume and cancellation

Resume an existing thread:

```python
from codex import Codex, ThreadResumeOptions

client = Codex()
thread = client.resume_thread("thread_123", ThreadResumeOptions())
result = thread.run("Continue from the existing context")
```

Cancel a streamed run using the separate `signal=` argument:

```python
import threading

from codex import Codex

cancel = threading.Event()

client = Codex()
stream = client.run("Long running task", signal=cancel)

cancel.set()
for event in stream:
    print(event)
```

## Shared context

Use an explicit `Thread` when you want multiple runs to share conversation state:

```python
from codex import Codex, ThreadStartOptions

client = Codex()
thread = client.start_thread(ThreadStartOptions(cwd="/repo"))
print(thread.run_text("Summarize the repository"))
print(thread.run_text("Now list the likely risky areas"))
```

## Errors

High-level run helpers raise `ThreadRunError` when the terminal turn fails or is interrupted.
The exception keeps the final turn metadata so you can inspect the terminal status and any
structured server error.

```python
from codex import Codex
from codex.errors import ThreadRunError

client = Codex()

try:
    client.run_text("Run the failing command and fix it")
except ThreadRunError as exc:
    print(exc.terminal_status)
    if exc.turn is not None and exc.turn.error is not None:
        print(exc.turn.error.message)
```

## When to prefer `Codex`

Choose `Codex` when you want:

- the smallest API surface
- local automation with minimal setup
- simple request/response or protocol-native streaming without managing the full app-server client

If you need persistent connections, protocol-native events, typed tool handlers, or richer thread management, use [`AppServerClient`](app_server.md).
