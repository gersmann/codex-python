# codex-python

Python SDK for Codex with bundled `codex` binaries inside platform wheels.

This package exposes two supported APIs:

- `Codex`: a simple, local convenience interface backed by a private stdio app-server session
- `AppServerClient`: a richer app-server client for thread management, streaming events, approvals, and typed protocol access

Canonical import paths:

- use `from codex import ...` for the high-level `Codex` facade
- use `from codex.app_server import ...` for the raw app-server client and app-server option types

## Install

```bash
pip install codex-python
```

## Which API should I use?

### `Codex`

Use `Codex` when you want the smallest surface area for local automation:

- one private local app-server session per `Codex` instance
- stateless `run*()` convenience (fresh internal thread per call)
- stateful thread workflows when needed via `start_thread()` / `resume_thread()`
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
summary = client.run_text("Diagnose the failing tests and propose a fix")
print(summary)
```

More `Codex` examples: [docs/exec_api.md](docs/exec_api.md)

## Quickstart: `AppServerClient`

```python
from codex.app_server import AppServerClient, AppServerClientInfo, AppServerInitializeOptions

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
For websocket transport, install the optional extra: `pip install "codex-python[websocket]"`.

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
payload = client.run_json("Summarize repository status", TurnOptions(output_schema=schema))
print(payload["summary"])
```

### `AppServerClient`

```python
from pydantic import BaseModel

from codex.app_server import AppServerClient, AppServerTurnOptions


class Summary(BaseModel):
    summary: str


with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    result = thread.run_model(
        "Summarize repository status",
        Summary,
    )
    print(result.summary)
```

`run_model()` uses `Summary` both as the validation model and, by default, as the output schema sent
to Codex. If you want JSON back without validation, you can also pass the model class directly to
`output_schema`, for example `thread.run_json(..., AppServerTurnOptions(output_schema=Summary))`.

## Streaming

### `Codex` stream

```python
from codex import Codex
from codex.protocol import types as protocol

client = Codex()
stream = client.run("Investigate this bug")
for event in stream:
    if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
        print(event.params.delta, end="", flush=True)

print()
```

`Codex.run*()` starts a fresh internal thread for each call. Use
`start_thread()` or `resume_thread()` when you want later runs to share context.

High-level `Codex` helpers raise `ThreadRunError` on failed or interrupted terminal turns and
preserve the final turn metadata on the exception for debugging and UI handling.

### App-server stream

```python
from codex.app_server import AppServerClient
from codex.protocol import types as protocol

with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    stream = thread.run("Investigate this bug")

    for event in stream:
        if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
            print(event.params.delta, end="", flush=True)

    print()
```

Advanced app-server usage, including typed stable RPC domains such as `client.models` and the raw `client.rpc` fallback: [docs/app_server_advanced.md](docs/app_server_advanced.md)

## Examples

- [examples/basic_conversation.py](examples/basic_conversation.py): minimal `Codex` flow
- [examples/app_server_conversation.py](examples/app_server_conversation.py): minimal app-server flow
- [examples/app_server_websocket_conversation.py](examples/app_server_websocket_conversation.py): minimal websocket app-server flow
- [examples/app_server_stream_events.py](examples/app_server_stream_events.py): protocol-native app-server streaming
- [examples/app_server_tool_handler.py](examples/app_server_tool_handler.py): typed app-server request handling

## Bundled binary behavior

By default, the SDK resolves the bundled binary at:

`codex/vendor/<target-triple>/codex/{codex|codex.exe}`

If the bundled binary is not present, for example in a source checkout, the SDK falls back to
`codex` on `PATH`.

You can override the executable path with:

- `CodexOptions(codex_path_override=...)`
- `codex.app_server.AppServerProcessOptions(codex_path_override=...)`

## Development

```bash
make lint
make test
```

`make test` emits a terminal coverage report, writes `coverage.xml`, and enforces the repository
coverage gate.

If you want to test vendored-binary behavior locally, fetch binaries into `codex/vendor`:

```bash
python scripts/fetch_codex_binary.py --target-triple x86_64-unknown-linux-musl
```
