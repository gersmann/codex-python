# codex-python

Python SDK for Codex with bundled `codex` binaries inside platform wheels.

This package exposes two supported APIs:

- `Codex`: a simple, local, CLI-backed interface built on `codex exec`
- `AppServerClient`: a richer app-server client for thread management, streaming events, approvals, and typed protocol access

## Install

```bash
pip install codex-python
```

## Which API should I use?

### `Codex`

Use `Codex` when you want the smallest surface area for local automation:

- one process per run
- simple request/response usage
- optional streaming over the exec event stream
- structured output via `TurnOptions(output_schema=...)`

### `AppServerClient`

Use `AppServerClient` when you want a deeper integration:

- persistent app-server connection
- thread objects and turn streams
- protocol-native notifications
- server-driven requests such as tool callbacks and approvals
- typed protocol models and raw JSON-RPC access when needed

## Quickstart: `Codex`

```python
from codex import Codex

client = Codex()
thread = client.start_thread()

result = thread.run("Diagnose the failing tests and propose a fix")
print(result.final_response)
```

More exec-based examples: [docs/exec_api.md](docs/exec_api.md)

## Quickstart: `AppServerClient`

```python
from codex import AppServerClient, AppServerClientInfo, AppServerInitializeOptions

initialize_options = AppServerInitializeOptions(
    client_info=AppServerClientInfo(
        name="my_integration",
        title="My Integration",
        version="0.1.0",
    )
)

with AppServerClient.connect_stdio(initialize_options=initialize_options) as client:
    thread = client.start_thread()
    summary = thread.run_text("Briefly summarize this repository's purpose.")
    print(summary)
```

More app-server examples: [docs/app_server.md](docs/app_server.md)

## Structured output

### `Codex`

```python
from codex import Codex, TurnOptions

schema = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

client = Codex()
thread = client.start_thread()
result = thread.run("Summarize repository status", TurnOptions(output_schema=schema))
print(result.final_response)
```

### `AppServerClient`

```python
from pydantic import BaseModel

from codex import AppServerClient


class Summary(BaseModel):
    summary: str


schema = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    result = thread.run_model(
        "Summarize repository status",
        Summary,
        outputSchema=schema,
    )
    print(result.summary)
```

## Streaming

### Exec stream

```python
from codex import Codex

client = Codex()
thread = client.start_thread()

stream = thread.run_streamed("Investigate this bug")
for event in stream.events:
    if event["type"] == "item.completed":
        print(event["item"])
```

### App-server stream

```python
from codex import AppServerClient
from codex.protocol import types as protocol

with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    stream = thread.run("Investigate this bug")

    for event in stream:
        if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
            print(event.params.delta, end="", flush=True)

    print()
```

Advanced app-server usage: [docs/app_server_advanced.md](docs/app_server_advanced.md)

## Examples

- [examples/basic_conversation.py](examples/basic_conversation.py): minimal `Codex` flow
- [examples/app_server_conversation.py](examples/app_server_conversation.py): minimal app-server flow
- [examples/app_server_stream_events.py](examples/app_server_stream_events.py): protocol-native app-server streaming
- [examples/app_server_tool_handler.py](examples/app_server_tool_handler.py): typed app-server request handling

## Bundled binary behavior

By default, the SDK resolves the bundled binary at:

`codex/vendor/<target-triple>/codex/{codex|codex.exe}`

If the bundled binary is not present, for example in a source checkout, the SDK falls back to
`codex` on `PATH`.

You can override the executable path with:

- `CodexOptions(codex_path_override=...)`
- `AppServerProcessOptions(codex_path_override=...)`

## Development

```bash
make lint
make test
```

If you want to test vendored-binary behavior locally, fetch binaries into `codex/vendor`:

```bash
python scripts/fetch_codex_binary.py --target-triple x86_64-unknown-linux-musl
```
