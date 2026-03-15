from __future__ import annotations

from codex.app_server import (
    AppServerClient,
    AppServerClientInfo,
    AppServerInitializeOptions,
    dynamic_tool,
)


class SupportDesk:
    @dynamic_tool
    def lookup_ticket(self, id: str) -> str:
        """Look up a support ticket by id."""
        return f"Ticket {id}: Login requests time out in eu-west-1."


def main() -> None:
    initialize_options = AppServerInitializeOptions(
        client_info=AppServerClientInfo(
            name="codex_python_dynamic_tool_example",
            title="codex-python Dynamic Tool Example",
            version="0.1.0",
        ),
        experimental_api=True,
    )
    support_desk = SupportDesk()

    with AppServerClient.connect_stdio(initialize_options=initialize_options) as client:
        thread = client.start_thread(tools=[support_desk.lookup_ticket])
        result = thread.run_text(
            "Use the lookup_ticket dynamic tool for ticket 123 and summarize the result."
        )
        print(result)


if __name__ == "__main__":
    main()
