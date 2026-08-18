"""Pack a multi-file glTF (.gltf + .bin + textures) into a single GLB.

Poly Haven models download as a JSON glTF plus relative includes. The viewer
loads meshes via ``/api/asset?path=...``, which cannot resolve those relatives.
Packing at fetch time keeps the catalog on one file, like OS3A / KayKit GLBs.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import struct
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def pack_gltf_to_glb(gltf_path: str | Path, dest: str | Path | None = None) -> Path:
    """Inline buffers and image URIs from a ``.gltf`` and write a ``.glb``.

    External files must stay inside the glTF's parent directory. Data URIs are
    accepted. The packed GLB is written next to the source unless ``dest`` is set.
    """
    source = Path(gltf_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"glTF file not found: {source}")
    if source.suffix.lower() != ".gltf":
        raise ValueError(f"pack_gltf_to_glb expects a .gltf file, got {source.suffix}")
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("glTF root must be a JSON object")
    root = source.parent
    blob = bytearray()
    buffer_starts: list[int] = []

    buffers = document.get("buffers")
    if buffers is None:
        buffers = []
        document["buffers"] = buffers
    if not isinstance(buffers, list):
        raise ValueError("glTF buffers must be an array")

    for index, buffer in enumerate(buffers):
        if not isinstance(buffer, dict):
            raise ValueError(f"glTF buffer {index} must be an object")
        raw = _load_buffer_bytes(buffer, root)
        start = _pad4(len(blob))
        if start > len(blob):
            blob.extend(b"\x00" * (start - len(blob)))
        buffer_starts.append(len(blob))
        blob.extend(raw)
        buffer.pop("uri", None)
        buffer["byteLength"] = len(raw)

    views = document.get("bufferViews")
    if not isinstance(views, list):
        views = []
        document["bufferViews"] = views
    for view in views:
        if not isinstance(view, dict):
            raise ValueError("glTF bufferView must be an object")
        buffer_index = int(view.get("buffer") or 0)
        if buffer_index < 0 or buffer_index >= len(buffer_starts):
            raise ValueError(f"bufferView references missing buffer {buffer_index}")
        view["buffer"] = 0
        view["byteOffset"] = buffer_starts[buffer_index] + int(view.get("byteOffset") or 0)

    images = document.get("images")
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, dict):
                raise ValueError("glTF image must be an object")
            uri = image.get("uri")
            if not isinstance(uri, str) or not uri or "bufferView" in image:
                continue
            raw, mime = _load_image_bytes(uri, root)
            start = _pad4(len(blob))
            if start > len(blob):
                blob.extend(b"\x00" * (start - len(blob)))
            offset = len(blob)
            blob.extend(raw)
            views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw)})
            image.pop("uri", None)
            image["bufferView"] = len(views) - 1
            if mime:
                image["mimeType"] = mime

    document["buffers"] = [{"byteLength": len(blob)}]
    packed = _write_glb(document, bytes(blob))
    target = Path(dest).resolve() if dest is not None else source.with_suffix(".glb")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(packed)
    return target


def _load_buffer_bytes(buffer: dict[str, Any], root: Path) -> bytes:
    uri = buffer.get("uri")
    if uri is None:
        raise ValueError("glTF buffer is missing a uri; cannot pack embedded-only JSON")
    if not isinstance(uri, str) or not uri:
        raise ValueError("glTF buffer uri must be a nonempty string")
    if uri.startswith("data:"):
        return _decode_data_uri(uri)[0]
    return _contained_file(root, uri).read_bytes()


def _load_image_bytes(uri: str, root: Path) -> tuple[bytes, str | None]:
    if uri.startswith("data:"):
        return _decode_data_uri(uri)
    path = _contained_file(root, uri)
    mime, _ = mimetypes.guess_type(path.name)
    return path.read_bytes(), mime


def _contained_file(root: Path, relative: str) -> Path:
    parsed = urlparse(relative)
    if parsed.scheme in {"http", "https"}:
        raise ValueError(f"Remote glTF URI is not packed: {relative}")
    path = unquote(parsed.path or relative)
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"glTF include escapes its directory: {relative!r}") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"glTF include not found: {relative}")
    return candidate


def _decode_data_uri(uri: str) -> tuple[bytes, str | None]:
    header, _, payload = uri.partition(",")
    if not payload:
        raise ValueError("Invalid data URI")
    mime = None
    if header.startswith("data:") and ";" in header:
        mime = header[5:].split(";", 1)[0] or None
    if ";base64" in header:
        return base64.b64decode(payload), mime
    return payload.encode("utf-8"), mime


def _pad4(length: int) -> int:
    remainder = length % 4
    return length if remainder == 0 else length + (4 - remainder)


def _write_glb(document: dict[str, Any], binary: bytes) -> bytes:
    json_bytes = json.dumps(document, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad
    bin_pad = (4 - (len(binary) % 4)) % 4
    bin_bytes = binary + (b"\x00" * bin_pad)
    total = 12 + 8 + len(json_bytes)
    chunks = [struct.pack("<I", len(json_bytes)), struct.pack("<I", JSON_CHUNK), json_bytes]
    if bin_bytes:
        total += 8 + len(bin_bytes)
        chunks.extend([struct.pack("<I", len(bin_bytes)), struct.pack("<I", BIN_CHUNK), bin_bytes])
    header = GLB_MAGIC + struct.pack("<II", GLB_VERSION, total)
    return header + b"".join(chunks)
