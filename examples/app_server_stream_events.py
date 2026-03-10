from __future__ import annotations

from codex import AppServerClient, AppServerClientInfo, AppServerInitializeOptions
from codex.protocol import types as protocol


def main() -> None:
    initialize_options = AppServerInitializeOptions(
        client_info=AppServerClientInfo(
            name="codex_python_example",
            title="codex-python Example",
            version="0.1.0",
        )
    )

    with AppServerClient.connect_stdio(initialize_options=initialize_options) as client:
        thread = client.start_thread()
        stream = thread.run("Briefly summarize this repository's purpose.")

        for event in stream:
            if isinstance(event, protocol.ItemAgentMessageDeltaNotification):
                print(event.params.delta, end="", flush=True)

        if not stream.text_deltas:
            print(stream.final_text, end="")

        print()


if __name__ == "__main__":
    main()
