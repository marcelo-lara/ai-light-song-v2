from __future__ import annotations

from importlib import import_module, util
from pathlib import Path
import os


OMNIZART_DRUM_MODEL_ENV = "OMNIZART_DRUM_MODEL_PATH"
OMNIZART_DRUM_MODEL_RELATIVE_PATH = Path("checkpoints") / "drum" / "drum_keras"
OMNIZART_DRUM_REQUIRED_FILES = (
    Path("saved_model.pb"),
    Path("configurations.yaml"),
    Path("variables") / "variables.index",
    Path("variables") / "variables.data-00000-of-00001",
)


def _find_omnizart_package_dir() -> Path:
    spec = util.find_spec("omnizart")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("omnizart is not installed")
    return Path(next(iter(spec.submodule_search_locations)))


def _validate_model_dir(model_dir: Path) -> Path:
    missing = [str(model_dir / relative_path) for relative_path in OMNIZART_DRUM_REQUIRED_FILES if not (model_dir / relative_path).exists()]
    if missing:
        raise ImportError(
            "Omnizart drum checkpoint is incomplete. Missing files: "
            + ", ".join(missing)
        )
    return model_dir


def resolve_omnizart_drum_model_path() -> tuple[Path, str]:
    env_model_path = os.environ.get(OMNIZART_DRUM_MODEL_ENV)
    if env_model_path:
        return _validate_model_dir(Path(env_model_path).expanduser().resolve()), "env"

    package_dir = _find_omnizart_package_dir()
    packaged_model_dir = package_dir / OMNIZART_DRUM_MODEL_RELATIVE_PATH
    return _validate_model_dir(packaged_model_dir), "package"


def load_omnizart_drum_runtime() -> tuple[object, Path, str]:
    try:
        drum_module = import_module("omnizart.drum")
    except ImportError as exc:
        raise ImportError("omnizart drum runtime is not available") from exc

    model_path, model_source = resolve_omnizart_drum_model_path()
    app = getattr(drum_module, "app", None)
    if app is None:
        raise ImportError("omnizart.drum does not expose an app instance")
    return app, model_path, model_source