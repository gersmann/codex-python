from __future__ import annotations

from codex import AppServerClient, AppServerClientInfo, AppServerInitializeOptions


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
        thread = client.start_thread()
        stream = thread.run("Briefly summarize this repository's purpose.")
        stream.wait()
        print(stream.final_text)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
