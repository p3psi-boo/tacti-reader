from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import TactiReader

__all__ = ["TactiReader"]


def __getattr__(name: str):
    if name == "TactiReader":
        from .main_window import TactiReader

        return TactiReader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
