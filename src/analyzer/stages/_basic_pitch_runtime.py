from __future__ import annotations

from importlib import import_module, util
from pathlib import Path
import sys
import types
from typing import Callable


TFLITE_MODEL_RELATIVE_PATH = Path("saved_models") / "icassp_2022" / "nmp.tflite"


def _find_basic_pitch_package_dir() -> Path:
    package = sys.modules.get("basic_pitch")
    if package is not None:
        package_paths = getattr(package, "__path__", None)
        if package_paths:
            return Path(next(iter(package_paths)))

    spec = util.find_spec("basic_pitch")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("basic-pitch is not installed")
    return Path(next(iter(spec.submodule_search_locations)))


def _bootstrap_tflite_package(package_dir: Path) -> Path:
    try:
        import tflite_runtime.interpreter  # noqa: F401
    except ImportError as exc:
        raise ImportError("basic-pitch requires tflite-runtime") from exc

    model_path = package_dir / TFLITE_MODEL_RELATIVE_PATH
    if not model_path.exists():
        raise ImportError(f"basic-pitch TFLite model not found at {model_path}")

    package = sys.modules.get("basic_pitch")
    if package is None:
        package = types.ModuleType("basic_pitch")
        sys.modules["basic_pitch"] = package

    package.__path__ = [str(package_dir)]
    package.CT_PRESENT = False
    package.ONNX_PRESENT = False
    package.TF_PRESENT = False
    package.TFLITE_PRESENT = True
    package.ICASSP_2022_MODEL_PATH = model_path
    return model_path


def load_basic_pitch_predict() -> tuple[Path, Callable[..., tuple[dict, object, list[tuple[float, float, int, float, list[int] | None]]]]]:
    package_dir = _find_basic_pitch_package_dir()
    model_path = _bootstrap_tflite_package(package_dir)
    inference = import_module("basic_pitch.inference")
    return model_path, inference.predict
