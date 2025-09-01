import importlib.util
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Callable

try:
    import yaml  # pip install pyyaml
except ImportError as e:
    raise SystemExit("Missing dependency: PyYAML. Install with `pip install pyyaml`.") from e

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ProviderEntry:
    """
    Holds constructors/factories only. You call these to get a NEW instance per camera.
    """
    name: str                     # "Axis", "Test", "Z3"
    camera_type: str              # same as 'type' in YAML
    control_cls: type             # e.g., VapixControl (a class; call it to get a NEW object)
    source_bin_factory: Callable  # e.g., create_source_bin(index, camera) -> Gst.Bin
    kwargs: Dict[str, Any]        # default kwargs for control_cls(...)

    # Convenience helpers to ensure a new object is created on each call
    def make_control(self, camera, **overrides):
        params = {**self.kwargs, **overrides} if overrides else self.kwargs
        return self.control_cls(camera, **params)

    def make_source_bin(self, index: int, camera):
        # Factory signature is (index, camera) -> Gst.Bin
        return self.source_bin_factory(index, camera)


def _import_from_file(module_name: str, file_path: Path) -> ModuleType:
    file_path = file_path.resolve()
    cache_key = f"__file__::{file_path}"
    if cache_key in sys.modules:
        return sys.modules[cache_key]
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    sys.modules[cache_key] = mod
    return mod

def _get_class(mod: ModuleType, class_name: str) -> type:
    try:
        cls = getattr(mod, class_name)
    except AttributeError:
        raise ImportError(f"Class {class_name} not found in {getattr(mod, '__file__', mod.__name__)}")
    if not isinstance(cls, type):
        raise TypeError(f"{class_name} is not a class")
    return cls

def _get_callable(mod: ModuleType, symbol_name: str) -> Callable:
    try:
        fn = getattr(mod, symbol_name)
    except AttributeError:
        raise ImportError(f"Symbol {symbol_name} not found in {getattr(mod, '__file__', mod.__name__)}")
    if not callable(fn):
        raise TypeError(f"{symbol_name} is not callable")
    return fn

def load_provider_registry(config_path: str | Path) -> dict[str, ProviderEntry]:
    """
    Build a registry mapping camera_type -> ProviderEntry from providers.yaml.
    Each ProviderEntry exposes .make_control(...) and .make_source_bin(...),
    ensuring you create NEW instances per camera at runtime.
    """
    cfg_path = Path(config_path).resolve()
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    providers = (cfg.get("camera_providers") or {})
    registry: dict[str, ProviderEntry] = {}
    base_dir = cfg_path.parent

    for name, p in providers.items():
        if not p.get("enabled", False):
            logger.info("Provider '%s' disabled; skipping.", name)
            continue

        camera_type = p.get("type") or name
        controller_file = p.get("controller_file")
        controller_class = p.get("controller_class") or "CameraControl"
        source_bin_file = p.get("source_bin_file")
        source_bin_func = p.get("source_bin_func")  # your factory function
        kwargs = p.get("kwargs") or {}

        if not controller_file or not controller_class:
            logger.error("Provider '%s' missing controller_file/controller_class.", name)
            continue
        if not source_bin_file or not source_bin_func:
            logger.error("Provider '%s' must define source_bin_file and source_bin_func.", name)
            continue
        if not isinstance(kwargs, dict):
            logger.error("Provider '%s' kwargs must be a mapping.", name)
            continue

        try:
            ctrl_mod = _import_from_file(f"{name}_controller", (base_dir / controller_file))
            src_mod  = _import_from_file(f"{name}_sourcebin", (base_dir / source_bin_file))

            control_cls = _get_class(ctrl_mod, controller_class)
            source_bin_factory = _get_callable(src_mod, source_bin_func)

            entry = ProviderEntry(
                name=name,
                camera_type=camera_type,
                control_cls=control_cls,
                source_bin_factory=source_bin_factory,
                kwargs=kwargs,
            )
            registry[camera_type] = entry
            logger.debug("Registered provider '%s' for type '%s'", name, camera_type)

        except Exception as e:
            logger.error("Failed loading provider '%s': %s", name, e)

    if not registry:
        logger.warning("No providers registered. Check %s", cfg_path)
    return registry
