from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import stat

from aa_content.errors import UserFacingError


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str = field(repr=False)


def load_openai_config(workspace: Path) -> OpenAIConfig:
    env_path = workspace / ".env"
    if not env_path.is_file() or env_path.is_symlink():
        raise UserFacingError(
            f"Missing required configuration: OPENAI_API_KEY in {env_path}"
        )

    permissions = stat.S_IMODE(env_path.stat().st_mode)
    if permissions & 0o077:
        raise UserFacingError(
            f"Configuration file must be private to the current user: {env_path} "
            "(run chmod 600)"
        )

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise UserFacingError(
            f"Configuration file cannot be read safely: {env_path}"
        ) from error

    value: str | None = None
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise UserFacingError(
                f"Invalid configuration syntax in {env_path} at line {line_number}."
            )
        key, raw_value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        if value is not None:
            raise UserFacingError(
                f"Duplicate OPENAI_API_KEY in {env_path} at line {line_number}."
            )
        value = _unquote(raw_value.strip())

    if not value:
        raise UserFacingError(
            f"Missing required configuration: OPENAI_API_KEY in {env_path}"
        )
    return OpenAIConfig(api_key=value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
