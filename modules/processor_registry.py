"""
Registry for modality processors
"""
import logging
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, Optional, List, Any

from config.settings import AppSettings, MultimodalConfig
from .modality_processor import BaseModalityProcessor, ModalityType, TextProcessor, AudioProcessor, ImageProcessor

# Setup logging if not already configured
if not logging.getLogger().hasHandlers():
    AppSettings.setup_logging()

logger = logging.getLogger(__name__)

class ProcessorRegistry:
    """Registry for modality processors with plugin support"""

    def __init__(self):
        self._processors: Dict[ModalityType, BaseModalityProcessor] = {}
        self._load_builtin_processors()
        self._load_plugins()

    def _load_builtin_processors(self):
        """Load built-in processors"""
        try:
            from .concrete_processors import (
                create_text_processor, create_audio_processor, create_image_processor
            )

            # Always load text processor
            self.register_processor(ModalityType.TEXT, create_text_processor())

            # Load audio processor if enabled
            if MultimodalConfig.ENABLE_AUDIO_PROCESSING:
                self.register_processor(ModalityType.AUDIO, create_audio_processor())

            # Load image processor if enabled
            if MultimodalConfig.ENABLE_IMAGE_ANALYSIS:
                self.register_processor(ModalityType.IMAGE, create_image_processor())

        except Exception as e:
            logger.warning(f"Failed to load built-in processors: {str(e)}")

    def _load_plugins(self):
        """Load processors from plugins directory"""
        try:
            plugins_dir = Path(__file__).parent / "plugins"
            if not plugins_dir.exists():
                return

            for plugin_file in plugins_dir.glob("*.py"):
                if plugin_file.name.startswith("_"):
                    continue

                try:
                    self._load_plugin_file(plugin_file)
                except Exception as e:
                    logger.warning(f"Failed to load plugin {plugin_file.name}: {str(e)}")

        except Exception as e:
            logger.warning(f"Plugin loading failed: {str(e)}")

    def _load_plugin_file(self, plugin_file: Path):
        """Load a single plugin file"""
        try:
            module_name = f"modules.plugins.{plugin_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find processor classes
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseModalityProcessor) and
                        obj != BaseModalityProcessor):

                        # Create instance and register
                        try:
                            processor_instance = obj()  # type: ignore
                            # Determine modality from class hierarchy
                            modality = self._determine_modality_from_class(obj)
                            if modality:
                                self.register_processor(modality, processor_instance)
                                logger.info(f"Loaded plugin processor: {name} for {modality.value}")
                        except Exception as e:
                            logger.warning(f"Failed to instantiate plugin processor {name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_file}: {str(e)}")
            raise

    def _determine_modality_from_class(self, cls) -> Optional[ModalityType]:
        """Determine modality from class inheritance"""
        if issubclass(cls, TextProcessor):
            return ModalityType.TEXT
        elif issubclass(cls, AudioProcessor):
            return ModalityType.AUDIO
        elif issubclass(cls, ImageProcessor):
            return ModalityType.IMAGE
        return None

    def register_processor(self, modality: ModalityType, processor: BaseModalityProcessor):
        """Register a processor for a modality"""
        self._processors[modality] = processor
        logger.info(f"Registered processor for {modality.value}")

    def get_processor(self, modality: ModalityType) -> Optional[BaseModalityProcessor]:
        """Get processor for a modality"""
        return self._processors.get(modality)

    def list_modalities(self) -> List[ModalityType]:
        """List supported modalities"""
        return list(self._processors.keys())
