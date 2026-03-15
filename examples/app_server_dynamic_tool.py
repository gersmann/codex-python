from __future__ import annotations

from codex.app_server import (
    AppServerClient,
    AppServerClientInfo,
    AppServerInitializeOptions,
    AppServerThreadStartOptions,
)
from codex.protocol import types as protocol


def handle_tool_call(request: protocol.ItemToolCallRequest) -> dict[str, object]:
    ticket_id = str(request.params.arguments["id"])
    return {
        "contentItems": [
            {
                "type": "text",
                "text": f"Ticket {ticket_id}: Login requests time out in eu-west-1.",
            }
        ]
    }


def main() -> None:
    initialize_options = AppServerInitializeOptions(
        client_info=AppServerClientInfo(
            name="codex_python_dynamic_tool_example",
            title="codex-python Dynamic Tool Example",
            version="0.1.0",
        ),
        experimental_api=True,
    )

    thread_options = AppServerThreadStartOptions(
        dynamic_tools=[
            protocol.DynamicToolSpec(
                name="lookup_ticket",
                description="Look up a support ticket by id.",
                inputSchema={
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            )
        ]
    )

    with AppServerClient.connect_stdio(initialize_options=initialize_options) as client:
        client.on_request(
            "item/tool/call",
            handle_tool_call,
            request_model=protocol.ItemToolCallRequest,
        )
        thread = client.start_thread(thread_options)
        result = thread.run_text(
            "Use the lookup_ticket dynamic tool for ticket 123 and summarize the result."
        )
        print(result)


if __name__ == "__main__":
    main()
