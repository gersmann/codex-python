# App-Server API (`AppServerClient`)

`AppServerClient` connects to `codex app-server` and exposes a thread and stream API on top of the JSON-RPC protocol.

Use it when you need a deeper integration than `Codex` provides: persistent connections, typed protocol notifications, or server-driven requests.

Import the raw app-server surface from `codex.app_server`, not from the top-level `codex` facade.

## Happy path

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

## Core objects

- `AppServerClient`: manages the app-server connection
- `AppServerThread`: represents a server-side thread
- `TurnStream`: iterates over typed protocol notifications for a turn

Async equivalents are also available:

- `AsyncAppServerClient`
- `AsyncAppServerThread`
- `AsyncTurnStream`

`AsyncAppServerClient.connect_stdio()` and `connect_websocket()` return an already started client.

If you use websocket transport, install the optional extra:

```bash
pip install "codex-python[websocket]"
```

`connect_websocket()` also accepts `AppServerWebSocketOptions` for explicit bearer auth,
headers, subprotocols, and connection timeouts.

A minimal websocket example is available at
[`examples/app_server_websocket_conversation.py`](../examples/app_server_websocket_conversation.py).

## Starting and resuming threads

```python
from codex.app_server import AppServerClient

with AppServerClient.connect_stdio() as client:
    new_thread = client.start_thread()
    existing_thread = client.resume_thread("thr_123")
```

Thread objects expose lifecycle methods such as `refresh()`, `fork()`, `archive()`, `rollback()`, `compact()`, and `set_name()`.

## Running turns

### `run()`

Use `run()` when you want to consume protocol-native notifications:

```python
from codex.app_server import AppServerClient
from codex.protocol import types as protocol

with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    stream = thread.run("Investigate the failing tests")

    for event in stream:
        if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
            print(event.params.delta, end="", flush=True)
```

### `run_text()`

Use `run_text()` when you only want the final assistant text:

```python
with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    summary = thread.run_text("Summarize the repository")
```

### `run_json()` and `run_model()`

Use these helpers when the turn is expected to return structured JSON:

```python
from pydantic import BaseModel

from codex.app_server import AppServerClient, AppServerTurnOptions


class Summary(BaseModel):
    answer: str


schema = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}

with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    payload = thread.run_json(
        "Return JSON matching the schema",
        AppServerTurnOptions(output_schema=schema),
    )
    payload_from_model = thread.run_json(
        "Return JSON matching the schema",
        AppServerTurnOptions(output_schema=Summary),
    )
    result = thread.run_model("Return JSON matching the schema", Summary)
```

`run_model()` validates the final assistant message text with `pydantic` and uses the model class as
the output schema by default. If you want JSON back without validation, you can also pass a
Pydantic model class directly to `AppServerTurnOptions(output_schema=...)`.

## Working with `TurnStream`

`TurnStream` keeps the protocol-native event stream, but also aggregates the final state for convenience:

- `final_text`
- `final_message`
- `final_turn`
- `items`
- `usage`
- `text_deltas`
- `final_json()`
- `final_model(Model)`

Example:

```python
with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    stream = thread.run("Summarize the repository")
    stream.wait()
    print(stream.final_text)
```

## Sync and async usage

The sync client mirrors the stable blocking workflow and the current stable typed RPC domains such as `client.models`, `client.account`, `client.config`, and `client.command`.

The async client remains the canonical surface for lower-level extensibility and future protocol expansion:

```python
from codex.app_server import AsyncAppServerClient


async def main() -> None:
    client = await AsyncAppServerClient.connect_stdio()
    try:
        thread = await client.start_thread()
        summary = await thread.run_text("Summarize the repository")
        print(summary)
    finally:
        await client.close()
```

For unsupported or experimental methods, use `client.rpc` on either client instead of expecting full sync/async wrapper parity for every future protocol addition.

For lower-level RPC access, typed request handlers, and protocol-native event iteration patterns, see [app_server_advanced.md](app_server_advanced.md).
