from __future__ import annotations

import os

from codex.app_server import (
    AppServerClient,
    AppServerClientInfo,
    AppServerInitializeOptions,
    AppServerWebSocketOptions,
)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(
            f"Set {name} to the websocket endpoint for codex app-server before running this example."
        )
    return value


def main() -> None:
    websocket_url = _require_env("CODEX_APP_SERVER_WEBSOCKET_URL")
    bearer_token = os.environ.get("CODEX_APP_SERVER_BEARER_TOKEN")

    initialize_options = AppServerInitializeOptions(
        client_info=AppServerClientInfo(
            name="codex_python_websocket_example",
            title="codex-python WebSocket Example",
            version="0.1.0",
        ),
    )
    websocket_options = AppServerWebSocketOptions(
        bearer_token=bearer_token,
        open_timeout=10,
        close_timeout=10,
    )

    with AppServerClient.connect_websocket(
        websocket_url,
        websocket_options=websocket_options,
        initialize_options=initialize_options,
    ) as client:
        thread = client.start_thread()
        summary = thread.run_text("Briefly summarize this repository's purpose.")
        print(summary)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
