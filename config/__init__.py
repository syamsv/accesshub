import threading
from .config import Config, ConfigError

_instance: Config | None = None
_init_lock = threading.Lock()


def init(env_file: str | None = ".env", required: list[str] | None = None) -> "Config":
    """Initialize the config package, loading env vars and validating required keys.

    Thread-safe: concurrent calls block until the first completes; subsequent
    calls re-initialize under the same lock so env-var writes never interleave.
    """
    global _instance
    with _init_lock:
        _instance = Config(env_file=env_file, required=required)
        return _instance


def __getattr__(name: str):
    if _instance is None:
        raise ConfigError(
            f"config.{name} accessed before init(). Call config.init() first."
        )
    return getattr(_instance, name)
