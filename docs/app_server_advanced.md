# Advanced App-Server Usage

This guide covers the lower-level app-server surface that sits under the thread convenience helpers.

Use it when you need typed stable RPC domains, protocol-native events, raw JSON-RPC fallbacks, or typed handlers for server-driven requests.

Import this surface from `codex.app_server`; the top-level `codex` package is reserved for the higher-level `Codex` facade.

## Protocol-native event iteration

`thread.run()` returns a `TurnStream` that yields generated protocol models from `codex.protocol.types`.

```python
from codex.app_server import AppServerClient
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

## Typed stable RPC domains

The advanced client exposes typed domain clients for stable non-thread RPC methods:

```python
from codex.app_server import AppServerClient

with AppServerClient.connect_stdio() as client:
    models = client.models.list(limit=20, include_hidden=False)
    print(models.data[0].displayName)

    account = client.account.read()
    print(account.requiresOpenaiAuth)

    result = client.command.exec(command=["git", "status"], cwd="/repo")
    print(result.exitCode)
```

These domain clients cover the stable RPC surface that does not naturally belong on a thread object, including `models`, `apps`, `skills`, `account`, `config`, `mcp_servers`, `feedback`, `command`, `external_agent_config`, and `windows_sandbox`.

The concrete sync wrapper classes behind these attributes are internal implementation details. Rely on `client.models` and the other domain attributes instead of importing wrapper types directly.

## Raw JSON-RPC

The `rpc` client remains the low-level escape hatch for experimental methods, version-skewed endpoints, or anything that does not have a typed wrapper yet.

```python
from codex.app_server import AppServerClient

with AppServerClient.connect_stdio() as client:
    result = client.rpc.request("experimentalFeature/list", {"limit": 20})
    print(result)
```

If you want typed results, use `request_typed()` with one of the Pydantic models from `codex.app_server.models` or `codex.protocol.types`.

## Connection-wide notifications

Use `client.events.subscribe()` when you want notifications outside a single turn stream.

```python
from codex.app_server import AppServerClient, GenericNotification

with AppServerClient.connect_stdio() as client:
    subscription = client.events.subscribe({"codex/event/mcp_startup_update"})
    try:
        event = subscription.next()
        if isinstance(event, GenericNotification):
            print(event.method, event.params)
    finally:
        subscription.close()
```

## Typed request handlers

Use `on_request()` when the server sends a JSON-RPC request that expects a client response.

```python
from codex.app_server import AppServerClient
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

For a complete dynamic-tool example that both registers `dynamic_tools` on
`start_thread()` and handles the resulting `item/tool/call` requests, see
[`examples/app_server_dynamic_tool.py`](../examples/app_server_dynamic_tool.py).

## When to use the advanced surface

Prefer the advanced app-server APIs when you need:

- stable typed access to lower-level RPC domains
- exact access to generated protocol notifications
- lower-level JSON-RPC methods not wrapped by a thread helper
- typed responses to server-driven requests
- explicit control over protocol details in a host integration

If you only want the final answer or a validated JSON payload, prefer the simpler thread helpers in [app_server.md](app_server.md).
