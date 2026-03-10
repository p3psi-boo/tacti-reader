import json
import os
from typing import Any, Callable, Dict

from .constants import GLOBAL_CONFIG_FILE


class ConfigManager:
    def __init__(self, global_config_file: str = GLOBAL_CONFIG_FILE):
        self.global_config_file = global_config_file

    def load_global_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.global_config_file):
            return {}
        try:
            with open(self.global_config_file, "r") as f:
                data = json.load(f)
            return data.get("global_config", {})
        except Exception:
            return {}

    def save_global_config(self, global_config: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.global_config_file), exist_ok=True)
        with open(self.global_config_file, "w") as f:
            json.dump({"global_config": global_config}, f, indent=2)

    def load_document_config(self, config_file: str | None) -> Dict[str, Any]:
        if not config_file or not os.path.exists(config_file):
            return {}
        with open(config_file, "r") as f:
            return json.load(f)

    def save_document_config(
        self,
        config_file: str | None,
        data: Dict[str, Any],
        serializer: Callable[[Any], Any] | None = None,
    ) -> None:
        if not config_file:
            return
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2, default=serializer)
