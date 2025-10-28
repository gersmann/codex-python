from __future__ import annotations

from codex import Codex


def main() -> None:
    client = Codex()
    thread = client.start_thread()
    result = thread.run("Briefly summarize this repository's purpose.")
    print(result.final_response)


if __name__ == "__main__":
    main()
