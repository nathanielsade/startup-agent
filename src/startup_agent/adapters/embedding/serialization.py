import numpy as np


def to_bytes(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> list[float]:
    return np.frombuffer(blob, dtype=np.float32).tolist()
