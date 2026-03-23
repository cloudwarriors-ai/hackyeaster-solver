"""Common CTF decode/encode/transform utilities."""

from __future__ import annotations

import base64
import codecs
import hashlib
import re
import string
from urllib.parse import unquote


# ── Flag validation ──────────────────────────────────────────────

FLAG_RE = re.compile(r"he20\d{2}\{[^}]+\}")


def validate_flag(text: str) -> dict:
    """Check if text matches HackyEaster flag format."""
    match = FLAG_RE.search(text)
    if match:
        return {"valid": True, "flag": match.group(0)}
    return {"valid": False, "flag": None, "input": text}


# ── Decode functions ─────────────────────────────────────────────

def decode(data: str, encoding: str) -> str:
    """Decode data using the specified encoding."""
    encoding = encoding.lower().strip()
    decoders = {
        "base64": _decode_base64,
        "b64": _decode_base64,
        "hex": _decode_hex,
        "url": _decode_url,
        "binary": _decode_binary,
        "morse": _decode_morse,
        "decimal": _decode_decimal,
        "octal": _decode_octal,
        "base32": _decode_base32,
    }
    fn = decoders.get(encoding)
    if fn is None:
        return f"Unknown encoding: {encoding}. Available: {', '.join(sorted(decoders))}"
    try:
        return fn(data)
    except Exception as e:
        return f"Decode error ({encoding}): {e}"


def _decode_base64(data: str) -> str:
    # Try standard, then URL-safe
    cleaned = data.strip()
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            padded = cleaned + "=" * (-len(cleaned) % 4)
            return decoder(padded).decode("utf-8", errors="replace")
        except Exception:
            continue
    return "Failed to decode base64"


def _decode_base32(data: str) -> str:
    cleaned = data.strip().upper()
    padded = cleaned + "=" * (-len(cleaned) % 8)
    return base64.b32decode(padded).decode("utf-8", errors="replace")


def _decode_hex(data: str) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", data)
    return bytes.fromhex(cleaned).decode("utf-8", errors="replace")


def _decode_url(data: str) -> str:
    return unquote(data)


def _decode_binary(data: str) -> str:
    bits = re.sub(r"[^01]", " ", data).split()
    return "".join(chr(int(b, 2)) for b in bits if len(b) == 8)


def _decode_morse(data: str) -> str:
    morse_map = {
        ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
        "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
        "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
        ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
        "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
        "--..": "Z", "-----": "0", ".----": "1", "..---": "2",
        "...--": "3", "....-": "4", ".....": "5", "-....": "6",
        "--...": "7", "---..": "8", "----.": "9",
    }
    words = data.strip().split("  ")
    result = []
    for word in words:
        chars = word.strip().split(" ")
        result.append("".join(morse_map.get(c, "?") for c in chars if c))
    return " ".join(result)


def _decode_decimal(data: str) -> str:
    nums = re.findall(r"\d+", data)
    return "".join(chr(int(n)) for n in nums if 0 < int(n) < 0x110000)


def _decode_octal(data: str) -> str:
    nums = re.findall(r"[0-7]+", data)
    return "".join(chr(int(n, 8)) for n in nums if 0 < int(n, 8) < 0x110000)


# ── Transform functions ──────────────────────────────────────────

def transform(data: str, method: str, **params) -> str:
    """Apply a transformation to data."""
    method = method.lower().strip()
    transforms = {
        "caesar": _transform_caesar,
        "rot13": _transform_rot13,
        "swap_pairs": _transform_swap_pairs,
        "reverse": _transform_reverse,
        "rail_fence": _transform_rail_fence,
        "vigenere": _transform_vigenere,
        "xor": _transform_xor,
        "atbash": _transform_atbash,
        "caesar_bruteforce": _transform_caesar_bruteforce,
    }
    fn = transforms.get(method)
    if fn is None:
        return f"Unknown method: {method}. Available: {', '.join(sorted(transforms))}"
    try:
        return fn(data, **params)
    except Exception as e:
        return f"Transform error ({method}): {e}"


def _transform_caesar(data: str, shift: int = 3, **_) -> str:
    result = []
    for ch in data:
        if ch in string.ascii_lowercase:
            result.append(chr((ord(ch) - ord("a") + shift) % 26 + ord("a")))
        elif ch in string.ascii_uppercase:
            result.append(chr((ord(ch) - ord("A") + shift) % 26 + ord("A")))
        else:
            result.append(ch)
    return "".join(result)


def _transform_caesar_bruteforce(data: str, **_) -> str:
    lines = []
    for shift in range(26):
        lines.append(f"shift={shift:2d}: {_transform_caesar(data, shift)}")
    return "\n".join(lines)


def _transform_rot13(data: str, **_) -> str:
    return codecs.decode(data, "rot_13")


def _transform_swap_pairs(data: str, **_) -> str:
    result = list(data)
    for i in range(0, len(result) - 1, 2):
        result[i], result[i + 1] = result[i + 1], result[i]
    return "".join(result)


def _transform_reverse(data: str, **_) -> str:
    return data[::-1]


def _transform_rail_fence(data: str, rails: int = 3, **_) -> str:
    if rails < 2:
        return data
    n = len(data)
    pattern = [0] * n
    idx = 0
    for rail in range(rails):
        step1 = 2 * (rails - 1 - rail) if rail < rails - 1 else 2 * (rails - 1)
        step2 = 2 * rail if rail > 0 else 2 * (rails - 1)
        i = rail
        use_step1 = True
        while i < n:
            pattern[i] = idx
            idx += 1
            step = step1 if use_step1 else step2
            if step == 0:
                step = step2 if use_step1 else step1
            i += step
            use_step1 = not use_step1
    result = [""] * n
    for pos, order in enumerate(pattern):
        if order < n:
            result[pos] = data[order]
    return "".join(result)


def _transform_vigenere(data: str, key: str = "key", decrypt: bool = True, **_) -> str:
    if not key:
        return "Vigenere requires a 'key' parameter"
    result = []
    key_idx = 0
    for ch in data:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            k = ord(key[key_idx % len(key)].lower()) - ord("a")
            shift = -k if decrypt else k
            result.append(chr((ord(ch) - base + shift) % 26 + base))
            key_idx += 1
        else:
            result.append(ch)
    return "".join(result)


def _transform_xor(data: str, key: int = 0, **_) -> str:
    if key == 0:
        # Bruteforce single-byte XOR, show printable results
        lines = []
        for k in range(1, 256):
            decoded = "".join(chr(ord(c) ^ k) for c in data)
            if all(c.isprintable() or c in "\n\t" for c in decoded):
                lines.append(f"key=0x{k:02x}: {decoded}")
        return "\n".join(lines[:30]) if lines else "No printable results found"
    return "".join(chr(ord(c) ^ key) for c in data)


def _transform_atbash(data: str, **_) -> str:
    result = []
    for ch in data:
        if ch in string.ascii_lowercase:
            result.append(chr(ord("z") - (ord(ch) - ord("a"))))
        elif ch in string.ascii_uppercase:
            result.append(chr(ord("Z") - (ord(ch) - ord("A"))))
        else:
            result.append(ch)
    return "".join(result)


# ── Hash functions ───────────────────────────────────────────────

def compute_hash(data: str, algorithm: str = "sha256") -> str:
    """Compute a hash of the data."""
    algorithm = algorithm.lower().strip()
    algos = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }
    fn = algos.get(algorithm)
    if fn is None:
        return f"Unknown algorithm: {algorithm}. Available: {', '.join(sorted(algos))}"
    return fn(data.encode("utf-8")).hexdigest()
