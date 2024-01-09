from typing import Callable


def is_command(func: Callable):
    return getattr(func, 'is_command', False)
