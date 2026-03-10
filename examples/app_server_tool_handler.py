from __future__ import annotations

from codex import AppServerClient, AppServerClientInfo, AppServerInitializeOptions
from codex.protocol import types as protocol


def handle_tool_call(request: protocol.ItemToolCallRequest) -> dict[str, object]:
    return {
        "contentItems": [
            {
                "type": "text",
                "text": f"Handled tool call for {request.params.tool}",
            }
        ]
    }


def main() -> None:
    initialize_options = AppServerInitializeOptions(
        client_info=AppServerClientInfo(
            name="codex_python_example",
            title="codex-python Example",
            version="0.1.0",
        ),
        experimental_api=True,
    )

    with AppServerClient.connect_stdio(initialize_options=initialize_options) as client:
        client.on_request(
            "item/tool/call",
            handle_tool_call,
            request_model=protocol.ItemToolCallRequest,
        )
        thread = client.start_thread()
        result = thread.run_text("Use the configured dynamic tool if the server asks for it.")
        print(result)


if __name__ == "__main__":
    main()
