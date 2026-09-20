from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.action import ActionRequest


class ActionAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def execute(self, request: ActionRequest) -> dict[str, Any]:
        """Execute an already-authorized action."""
        raise NotImplementedError
