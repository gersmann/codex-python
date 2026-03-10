# Exec API (`Codex`)

`Codex` is the simplest way to drive Codex from Python. It wraps `codex exec --experimental-json` and gives you a small thread-oriented API for request/response and streamed runs.

## Happy path

```python
from codex import Codex

client = Codex()
thread = client.start_thread()

result = thread.run("Diagnose the failing tests and propose a fix")
print(result.final_response)
print(result.items)
print(result.usage)
```

## Streaming

Use `run_streamed()` when you want access to the raw exec event stream:

```python
from codex import Codex

client = Codex()
thread = client.start_thread()

stream = thread.run_streamed("Investigate the flaky test")
for event in stream.events:
    print(event["type"])
```

## Structured output

```python
from codex import Codex, TurnOptions

schema = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}

client = Codex()
thread = client.start_thread()
result = thread.run("Return JSON matching the schema", TurnOptions(output_schema=schema))
print(result.final_response)
```

`RunResult.final_response` is still a string. If you need model validation or richer streaming, use the app-server client instead.

## Inputs

`Thread.run()` accepts either:

- a plain string
- a list of text and local-image input items

Example:

```python
from codex import Codex

client = Codex()
thread = client.start_thread()
result = thread.run(
    [
        {"type": "text", "text": "Describe these screenshots"},
        {"type": "local_image", "path": "./ui.png"},
    ]
)
```

## Resume and cancellation

Resume an existing thread:

```python
from codex import Codex

client = Codex()
thread = client.resume_thread("thread_123")
result = thread.run("Continue from the existing context")
```

Cancel a streamed run using `TurnOptions(signal=...)`:

```python
import threading

from codex import Codex, TurnOptions

cancel = threading.Event()

client = Codex()
thread = client.start_thread()
stream = thread.run_streamed("Long running task", TurnOptions(signal=cancel))

cancel.set()
for event in stream.events:
    print(event)
```

## When to prefer `Codex`

Choose `Codex` when you want:

- the smallest API surface
- local automation around `codex exec`
- simple request/response or raw exec event streaming

If you need persistent connections, protocol-native events, typed tool handlers, or richer thread management, use [`AppServerClient`](app_server.md).
