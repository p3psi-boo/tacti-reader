import hashlib
import os
import sys

from PyQt5.QtGui import QColor

from .constants import CONFIG_DIR


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_config_path(pdf_path: str) -> str:
    abs_path = os.path.abspath(pdf_path)
    hash_id = hashlib.md5(abs_path.encode("utf-8")).hexdigest()[:12]
    base_name = os.path.basename(pdf_path).replace(".", "_").replace(" ", "_")
    config_name = f"{base_name}_{hash_id}.json"
    return os.path.join(CONFIG_DIR, config_name)


def serialize_annotations(obj):
    if isinstance(obj, dict):
        return {k: serialize_annotations(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_annotations(item) for item in obj]
    if isinstance(obj, QColor):
        return obj.name()
    return obj
