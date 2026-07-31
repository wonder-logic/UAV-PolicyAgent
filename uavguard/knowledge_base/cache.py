"""Small in-memory cache utilities."""

from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class LocalLookupCache(Generic[K, V]):
    """Tiny LRU cache used for repeated drone lookups."""

    def __init__(self, max_items: int = 128) -> None:
        self.max_items = max_items
        self._store: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        value = self._store.get(key)
        if value is None:
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: K, value: V) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.max_items:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
