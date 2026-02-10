# codex-python

Python SDK for Codex with bundled `codex` binaries inside platform wheels.

The SDK mirrors the TypeScript SDK behavior:
- Spawns `codex exec --experimental-json`
- Streams JSONL events
- Supports thread resume, structured output schemas, images, sandbox/model options

## Install

```bash
pip install codex-python
```

## Quickstart

```python
from codex import Codex

client = Codex()
thread = client.start_thread()

result = thread.run("Diagnose the failing tests and propose a fix")
print(result.final_response)
print(result.items)
```

## Streaming

```python
from codex import Codex

client = Codex()
thread = client.start_thread()

stream = thread.run_streamed("Investigate this bug")
for event in stream.events:
    if event["type"] == "item.completed":
        print(event["item"])
    elif event["type"] == "turn.completed":
        print(event["usage"])
```

## Structured output

```python
from codex import Codex, TurnOptions

schema = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

client = Codex()
thread = client.start_thread()
result = thread.run("Summarize repository status", TurnOptions(output_schema=schema))
print(result.final_response)
```

## Input with local images

```python
from codex import Codex

client = Codex()
thread = client.start_thread()
result = thread.run(
    [
        {"type": "text", "text": "Describe these screenshots"},
        {"type": "local_image", "path": "./ui.png"},
        {"type": "local_image", "path": "./diagram.jpg"},
    ]
)
```

## Resume a thread

```python
from codex import Codex

client = Codex()
thread = client.resume_thread("thread_123")
thread.run("Continue from previous context")
```

## Options

- `CodexOptions`: `codex_path_override`, `base_url`, `api_key`, `config`, `env`
- `ThreadOptions`: `model`, `sandbox_mode`, `working_directory`, `skip_git_repo_check`, `model_reasoning_effort`, `network_access_enabled`, `web_search_mode`, `web_search_enabled`, `approval_policy`, `additional_directories`
- `TurnOptions`: `output_schema`, `signal`

## Cancellation

```python
import threading

from codex import Codex, TurnOptions

cancel = threading.Event()

client = Codex()
thread = client.start_thread()
stream = thread.run_streamed("Long running task", TurnOptions(signal=cancel))

cancel.set()
for event in stream.events:
    print(event)
```

## Bundled binary behavior

By default, the SDK resolves the bundled binary at:

`codex/vendor/<target-triple>/codex/{codex|codex.exe}`

If the bundled binary is not present (for example in a source checkout), the SDK falls back to
`codex` on `PATH`.

You can always override with `CodexOptions(codex_path_override=...)`.

## Development

```bash
make lint
make test
```

If you want to test vendored-binary behavior locally, fetch binaries into `codex/vendor`:

```bash
python scripts/fetch_codex_binary.py --target-triple x86_64-unknown-linux-musl
```
