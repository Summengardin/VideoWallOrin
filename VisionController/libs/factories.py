import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Literal, Optional, TypedDict, Union
import gi
import yaml
import importlib.util


sys.path.insert(0, "/app/")
from VisionController.libs.vw_types import Source, SourceType, Camera

logger = logging.getLogger(__name__)


# -----------------------------
# Models
# -----------------------------

# @dataclass
# class Camera:
#     """Minimal camera model used by the factory."""
#     id: str
#     type: str                # e.g., "Axis", "Test"
#     ip: Optional[str] = None
#     uri: Optional[str] = None


@dataclass
class ProviderEntry:
    """A single provider registration."""
    enabled: bool
    type: str
    controller_path: Optional[Path] = None
    controller_class: Optional[str] = None
    source_bin_path: Optional[Path] = None
    source_bin_func: Optional[str] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def has_controller(self) -> bool:
        return bool(self.controller_path and self.controller_class)

    def has_source_bin(self) -> bool:
        return bool(self.source_bin_path and self.source_bin_func)


class ProviderDict(TypedDict, total=False):
    enabled: bool
    type: str
    controller_file: str
    controller_class: str
    source_bin_file: str
    source_bin_func: str
    kwargs: Dict[str, Any]


class CameraFactory:
    """
    Loads camera providers from YAML and dynamically imports controller/source_bin modules by file path.

    - Control creation is per-camera (returns an instance of the provider controller class).
    - Source bin creation happens per source swap (returns whatever your create_source_bin provides, e.g., a Gst.Bin).
    """

    def __init__(self) -> None:
        # provider name (e.g., "Axis") -> ProviderEntry
        self.provider_registry: Dict[str, ProviderEntry] = {}
        # cache of loaded modules: generated module name -> module
        self._modules: Dict[str, ModuleType] = {}

    def _register_provider(self, name: str, data: ProviderDict) -> None:
        """Register a provider from a dict (parsed YAML)."""
        enabled = bool(data.get("enabled", False))
        ptype = str(data.get("type", name))

        controller_path = Path(data["controller_file"]).resolve() if data.get("controller_file") else None
        controller_class = str(data.get("controller_class")) if data.get("controller_class") else None

        source_bin_path = Path(data["source_bin_file"]).resolve() if data.get("source_bin_file") else None
        source_bin_func = str(data.get("source_bin_func")) if data.get("source_bin_func") else None

        kwargs = dict(data.get("kwargs", {}) or {})

        entry = ProviderEntry(
            enabled=enabled,
            type=ptype,
            controller_path=controller_path,
            controller_class=controller_class,
            source_bin_path=source_bin_path,
            source_bin_func=source_bin_func,
            kwargs=kwargs,
        )
        self.provider_registry[name] = entry
        logger.debug("Registered provider %s -> %s", name, entry)

    def load_providers_from_config_file(self, path: Union[str, Path]) -> None:
        """
        Read providers from YAML:
        camera_providers:
          Axis:
            enabled: true
            type: Axis
            controller_file: "/abs/path/vapix_control.py"
            controller_class: "VapixControl"
            source_bin_file: "/abs/path/nvuri_source_bin.py"
            source_bin_func: "create_source_bin"
            kwargs: {}
        """
        cfg_path = Path(path)
        if not cfg_path.exists():
            raise FileNotFoundError(f"Config file not found: {cfg_path}")

        with cfg_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        providers = raw.get("camera_providers")
        if not isinstance(providers, dict):
            raise ValueError("config.yaml must contain a 'camera_providers' mapping")

        self.provider_registry.clear()
        for name, pdata in providers.items():
            if not isinstance(pdata, dict):
                logger.warning("Skipping provider %r: value is not a mapping", name)
                continue
            self._register_provider(name, pdata)  # type: ignore[arg-type]

    def load_from_dict(self, providers: Dict[str, ProviderDict]) -> None:
        """
        Load providers from a dict structure.
        Example:
        {
            "Axis": {
                "enabled": true,
                "type": "Axis",
                "controller_file": "/abs/path/vapix_control.py",
                "controller_class": "VapixControl",
                "source_bin_file": "/abs/path/nvuri_source_bin.py",
                "source_bin_func": "create_source_bin",
                "kwargs": {}
            }
        }
        """
        self.provider_registry.clear()
        for name, pdata in providers.items():
            if not isinstance(pdata, dict):
                logger.warning("Skipping provider %r: value is not a mapping", name)
                continue
            self._register_provider(name, pdata)

    def _load_module(self, provider_name: str,  module_type: Literal["controller", "source_bin"]) -> Optional[ModuleType]:
        """
        Load a provider submodule by file path and cache it.
        module_type: "controller" | "source_bin"
        """
        entry = self.provider_registry.get(provider_name)
        if entry is None:
            raise KeyError(f'Camera provider "{provider_name}" not registered')

        # Determine the path to import
        if module_type == "controller":
            path = entry.controller_path
        elif module_type == "source_bin":
            path = entry.source_bin_path
        else:
            raise ValueError(f"Unknown module_type: {module_type}")

        if not path:
            logger.debug("Provider %s has no %s module path set.", provider_name, module_type)
            return None

        if not path.exists():
            raise FileNotFoundError(f"{module_type} module for {provider_name} not found: {path}")

        module_name = f"cameras.{provider_name}.{module_type}".replace(" ", "_")

        # Return cached module if already loaded
        if module_name in self._modules:
            return self._modules[module_name]

        # Build and exec module spec
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create import spec for {path}")

        module = importlib.util.module_from_spec(spec)
        # Insert into sys.modules to support relative imports inside the module (if any)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as e:
            # Cleanup on failure
            sys.modules.pop(module_name, None)
            raise ImportError(f"Failed to import {module_type} module '{path}': {e}") from e

        self._modules[module_name] = module
        logger.debug("Loaded module %s from %s", module_name, path)
        return module

    def create_camera_control(self, camera: Camera, **override_kwargs: Any) -> Optional[Any]:
        """
        Instantiate the provider's controller class for this camera.
        Expected controller __init__ signature: (camera: Camera, **kwargs)
        Returns the controller instance, or None if the provider has no controller configured/enabled.
        """
        entry = self._get_entry_for_camera(camera)
        if not entry.enabled:
            logger.info("Provider %s is disabled; no controller created.", camera.type)
            return None
        if not entry.has_controller():
            logger.debug("Provider %s has no controller defined.", camera.type)
            return None

        module = self._load_module(camera.type, "controller")
        assert module is not None  # has_controller() already checked that a path/class exists

        cls_name = entry.controller_class  # type: ignore[assignment]
        try:
            controller_cls = getattr(module, cls_name)
        except AttributeError as e:
            raise ImportError(f'Controller class "{cls_name}" not found in module {module.__name__}') from e

        kwargs = {**entry.kwargs, **override_kwargs}
        controller = controller_cls(camera, **kwargs)
        logger.debug("Created controller %s for camera %s", controller_cls.__name__, camera.id)
        return controller

    def create_source_bin(self, source_id: int, camera: Camera, **override_kwargs: Any) -> Any:
        """
        Invoke the provider's source-bin factory function for this camera.
        Expected function signature: create_source_bin(index: int, camera: Camera, **kwargs) -> Gst.Bin (or similar)
        Returns the constructed bin (whatever your function returns).
        """
        entry = self._get_entry_for_camera(camera)
        if not entry.enabled:
            raise RuntimeError(f'Provider "{camera.type}" is disabled; cannot create source bin.')

        if not entry.has_source_bin():
            raise RuntimeError(f'Provider "{camera.type}" has no source bin function configured.')

        module = self._load_module(camera.type, "source_bin")
        assert module is not None

        func_name = entry.source_bin_func  # type: ignore[assignment]
        try:
            factory_func: Callable[..., Any] = getattr(module, func_name)
        except AttributeError as e:
            raise ImportError(f'Source bin function "{func_name}" not found in module {module.__name__}') from e

        kwargs = {**entry.kwargs, **override_kwargs}
        bin_obj = factory_func(source_id, camera, **kwargs)

        from gi.repository import Gst
        Gst.debug_bin_to_dot_file(bin_obj, Gst.DebugGraphDetails.ALL, f"source_{source_id}_bin_{camera.type}")

        logger.debug(f"Created source bin via {func_name} for camera {camera.id}")
        return bin_obj

    def _get_entry_for_camera(self, camera: Camera) -> ProviderEntry:
        """Lookup ProviderEntry by camera.type with a case-insensitive fallback."""
        entry = self.provider_registry.get(camera.type)
        if entry:
            return entry
        # case-insensitive fallback
        for name, e in self.provider_registry.items():
            if name.lower() == camera.type.lower():
                return e
        raise KeyError(f'No provider entry found for camera.type="{camera.type}"')
    



if __name__ == "__main__":
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst


    # Example usage
    factory = CameraFactory()
    factory.load_from_dict({
        "Axis": {
            "enabled": True,
            "type": "Axis",
            "controller_file": "/app/VisionController/libs/cameras/vapix_control.py",
            "controller_class": "VapixControl",
            "source_bin_file": "/app/VisionController/libs/cameras/nvuri_source_bin.py",
            "source_bin_func": "create_source_bin",
            "kwargs": {}
        }
    })

    camera = Camera(id=1, ip="10.1.3.70", uri="rtsp://root:root@10.1.3.70/axis-media/media.amp?streamprofile=stream-1", type="Axis")
    source_bin = factory.create_source_bin(1, camera)
    control = factory.create_camera_control(camera)
    
    Gst.init(None)
    pipeline = Gst.Pipeline.new("test-pipeline")
    pipeline.add(source_bin)

    fakesink = Gst.ElementFactory.make("nveglglessink", "sink")
    if not fakesink:
        raise RuntimeError("Failed to create fakesink element")

    pipeline.add(fakesink)


    src_pad = source_bin.get_static_pad("src")
    sink_pad = fakesink.get_static_pad("sink")
    if not src_pad or not sink_pad:
        raise RuntimeError("Failed to get pads for linking")

    if src_pad.link(sink_pad) != Gst.PadLinkReturn.OK:
        raise RuntimeError("Failed to link source_bin to fakesink")

    pipeline.set_state(Gst.State.PLAYING)
    print("Pipeline is running. Press Ctrl+C to stop.")
    try:
        bus = pipeline.get_bus()
        while True:
            msg = bus.timed_pop_filtered(100 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS)
            if msg:
                break
    except KeyboardInterrupt:
        pass
    finally:
        Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, "test_pipeline")

        pipeline.set_state(Gst.State.NULL)