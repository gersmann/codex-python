from __future__ import annotations

from codex import Codex


def main() -> None:
    client = Codex()
    summary = client.run_text("Briefly summarize this repository's purpose.")
    print(summary)


if __name__ == "__main__":
    main()
