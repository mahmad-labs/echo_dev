from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable


def feature_hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    """Create a normalized hashing-trick text vector with no trained model dependency."""
    if not 16 <= dimensions <= 4096:
        raise ValueError("dimensions must be between 16 and 4096")
    tokens = re.findall(r"[\w'-]+", text.lower())
    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def batch_feature_hash_embedding(texts: Iterable[str], dimensions: int = 384) -> list[list[float]]:
    return [feature_hash_embedding(text, dimensions) for text in texts]
