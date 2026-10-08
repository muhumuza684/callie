import time
from dataclasses import dataclass, field


@dataclass
class Session:
    started: float = field(default_factory=time.monotonic)
    turns: list = field(default_factory=list)
