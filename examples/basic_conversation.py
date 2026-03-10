from __future__ import annotations

from codex import Codex


def main() -> None:
    client = Codex()
    thread = client.start_thread()
    summary = thread.run_text("Briefly summarize this repository's purpose.")
    print(summary)


if __name__ == "__main__":
    main()
