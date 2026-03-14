from __future__ import annotations

type CodexConfigValue = (
    str | int | float | bool | list["CodexConfigValue"] | dict[str, "CodexConfigValue"]
)
type CodexConfigObject = dict[str, CodexConfigValue]
