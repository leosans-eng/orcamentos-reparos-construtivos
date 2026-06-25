from collections.abc import Callable
from typing import Any

def hook_dropfiles(
    widget: Any,
    func: Callable[[list], None],
    force_unicode: bool = ...,
) -> None: ...
