"""Sample helper module for scanner extraction tests."""
from datetime import datetime


def format_time(value: datetime) -> str:
    return value.isoformat()


def _private_helper(value: int) -> int:
    return value * 2


class Foo:
    def method(self, x: int) -> int:
        return x + 1
