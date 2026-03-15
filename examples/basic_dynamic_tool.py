from __future__ import annotations

from codex import Codex, dynamic_tool


class SupportDesk:
    @dynamic_tool
    def lookup_ticket(self, id: str) -> str:
        """Look up a support ticket by id."""
        return f"Ticket {id}: Login requests time out in eu-west-1."


def main() -> None:
    support_desk = SupportDesk()
    client = Codex()
    summary = client.run_text(
        "Use the lookup_ticket dynamic tool for ticket 123 and summarize the result.",
        tools=[support_desk.lookup_ticket],
    )
    print(summary)


if __name__ == "__main__":
    main()
