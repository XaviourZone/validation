"""Hashing utilities for deterministic file checksums and message IDs."""

import hashlib
import uuid
from pathlib import Path
from typing import Union


def compute_file_hash(file_path: Union[str, Path], chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file efficiently using chunked reads."""
    hasher = hashlib.sha256()
    path = Path(file_path)
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_data_hash(data: Union[str, bytes]) -> str:
    """Compute SHA-256 hash of string or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_file_message_id(source: str, filename: str, file_size: int, mtime: float, file_hash: str) -> str:
    """Generate deterministic message ID for a file based on metadata and hash."""
    seed = f"{source}:{filename}:{file_size}:{mtime:.3f}:{file_hash}"
    hash_digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"file:{source.lower()}:{hash_digest[:24]}"


def generate_tcp_message_id(source: str) -> str:
    """Generate a unique message ID for a live streaming network message."""
    unique_id = uuid.uuid4().hex
    return f"tcp:{source.lower()}:{unique_id}"
