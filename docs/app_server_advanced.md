# Advanced App-Server Usage

This guide covers the lower-level app-server surface that sits under the thread convenience helpers.

Use it when you need protocol-native events, raw JSON-RPC calls, or typed handlers for server-driven requests.

## Protocol-native event iteration

`thread.run()` returns a `TurnStream` that yields generated protocol models from `codex.protocol.types`.

```python
from codex import AppServerClient
from codex.protocol import types as protocol

with AppServerClient.connect_stdio() as client:
    thread = client.start_thread()
    stream = thread.run("Investigate the failing tests")

    for event in stream:
        if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
            print(event.params.delta, end="", flush=True)
        elif isinstance(event, protocol.TurnCompletedNotificationModel):
            print("\nturn finished:", event.params.turn.status.root)
```

This is the right level when you want exact protocol semantics instead of a wrapper event layer.

## Raw JSON-RPC

The `rpc` client is the low-level escape hatch:

```python
from codex import AppServerClient

with AppServerClient.connect_stdio() as client:
    result = client.rpc.request("model/list", {"limit": 20})
    print(result)
```

If you want typed results, use `request_typed()` with one of the Pydantic models from `codex.app_server.models` or `codex.protocol.types`.

## Service namespaces

The convenience namespaces wrap common method prefixes:

- `client.models`
- `client.account`
- `client.config`
- `client.apps`
- `client.skills`
- `client.mcp_servers`
- `client.feedback`
- `client.experimental_features`
- `client.collaboration_modes`
- `client.windows_sandbox`

Example:

```python
with AppServerClient.connect_stdio() as client:
    models = client.models.call("list", {"limit": 20})
    print(models)
```

## Typed request handlers

Use `on_request()` when the server sends a JSON-RPC request that expects a client response.

```python
from codex import AppServerClient
from codex.protocol import types as protocol


def handle_tool_call(request: protocol.ItemToolCallRequest) -> dict[str, object]:
    return {
        "contentItems": [
            {
                "type": "text",
                "text": f"Handled {request.params.tool}",
            }
        ]
    }


with AppServerClient.connect_stdio() as client:
    client.on_request(
        "item/tool/call",
        handle_tool_call,
        request_model=protocol.ItemToolCallRequest,
    )
    thread = client.start_thread()
    thread.run_text("Use the configured dynamic tool if needed.")
```

The async client exposes the same pattern with async handlers.

## When to use the advanced surface

Prefer the advanced app-server APIs when you need:

- exact access to generated protocol notifications
- lower-level JSON-RPC methods not wrapped by a thread helper
- typed responses to server-driven requests
- explicit control over protocol details in a host integration

If you only want the final answer or a validated JSON payload, prefer the simpler thread helpers in [app_server.md](app_server.md).
