import os
from pathlib import Path


class ConfigError(Exception):
    pass


class Config:
    def __init__(
        self,
        env_file: str | None = ".env",
        required: list[str] | None = None,
    ):
        if env_file:
            self._load_env_file(env_file)

        if required:
            self._validate_required(required)

    # ------------------------------------------------------------------ #
    # attribute access  →  config.SLACK_BOT_TOKEN                         #
    # ------------------------------------------------------------------ #

    def __getattr__(self, name: str) -> str:
        value = os.environ.get(name)
        if value is None:
            raise ConfigError(f"Environment variable '{name}' is not set.")
        return value

    # ------------------------------------------------------------------ #
    # explicit getters                                                     #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return the env var value, or *default* if not set."""
        return os.environ.get(key, default)

    def require(self, *keys: str) -> None:
        """Raise ConfigError if any of *keys* are missing from the environment."""
        self._validate_required(list(keys))

    # ------------------------------------------------------------------ #
    # .env file loader                                                     #
    # ------------------------------------------------------------------ #

    def _load_env_file(self, path: str) -> None:
        """
        Parse a .env file and populate os.environ for any key not already set.
        Supports:
          KEY=value
          KEY="quoted value"
          KEY='quoted value'
          # comments
          export KEY=value
        """
        env_path = Path(path)
        if not env_path.exists():
            return  # missing .env is not an error — system env may be sufficient

        with env_path.open() as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # strip surrounding quotes
                if len(value) >= 2 and value[0] in ('"', "'") and value[0] == value[-1]:
                    value = value[1:-1]
                # system env takes precedence over .env file
                if key and key not in os.environ:
                    os.environ[key] = value

    # ------------------------------------------------------------------ #
    # validation                                                           #
    # ------------------------------------------------------------------ #

    def _validate_required(self, keys: list[str]) -> None:
        missing = [k for k in keys if not os.environ.get(k)]
        if missing:
            raise ConfigError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )
