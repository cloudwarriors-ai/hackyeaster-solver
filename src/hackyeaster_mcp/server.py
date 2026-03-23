"""HackyEaster MCP server — tools for Claude-driven CTF solving."""

from __future__ import annotations

import asyncio
import base64
import io
import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, ImageContent, Tool

from . import ctfutils, discovery, state
from .fetcher import download_bytes, fetch_page

app = Server("hackyeaster")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


# ── Tool definitions ─────────────────────────────────────────────

TOOLS = [
    Tool(
        name="he_discover_challenges",
        description="Scrape hackyeaster.com and return a list of available challenges with titles, URLs, descriptions, and embedded data.",
        inputSchema={
            "type": "object",
            "properties": {
                "dynamic": {
                    "type": "boolean",
                    "description": "Use headless browser (DynamicFetcher) for JS-rendered content. Default false.",
                    "default": False,
                },
            },
        },
    ),
    Tool(
        name="he_fetch_challenge",
        description="Fetch a specific challenge page and return parsed content: title, description, hints, code blocks, images, links.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The challenge page URL"},
                "dynamic": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="he_fetch_raw",
        description="Fetch any URL and return the raw HTML. Useful for following links or checking resources.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "dynamic": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="he_decode",
        description="Decode data using a specified encoding: base64, hex, url, binary, morse, decimal, octal, base32.",
        inputSchema={
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "The data to decode"},
                "encoding": {
                    "type": "string",
                    "description": "Encoding type: base64, hex, url, binary, morse, decimal, octal, base32",
                },
            },
            "required": ["data", "encoding"],
        },
    ),
    Tool(
        name="he_transform",
        description="Apply a cipher/transform: caesar (with shift param), rot13, swap_pairs, reverse, rail_fence (with rails param), vigenere (with key param), xor (with key param), atbash, caesar_bruteforce.",
        inputSchema={
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "The data to transform"},
                "method": {
                    "type": "string",
                    "description": "Transform method: caesar, rot13, swap_pairs, reverse, rail_fence, vigenere, xor, atbash, caesar_bruteforce",
                },
                "shift": {"type": "integer", "description": "Shift for caesar cipher"},
                "key": {
                    "description": "Key for vigenere (string) or xor (integer). For xor, 0 means bruteforce.",
                },
                "rails": {"type": "integer", "description": "Number of rails for rail_fence"},
                "decrypt": {"type": "boolean", "description": "Decrypt mode for vigenere", "default": True},
            },
            "required": ["data", "method"],
        },
    ),
    Tool(
        name="he_analyze_image",
        description="Download an image URL and return it as base64 for visual analysis. Also attempts QR code / barcode detection if pyzbar is available.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Image URL to download and analyze"},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="he_hash",
        description="Compute a hash of the given data. Algorithms: md5, sha1, sha256, sha512.",
        inputSchema={
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data to hash"},
                "algorithm": {"type": "string", "default": "sha256"},
            },
            "required": ["data"],
        },
    ),
    Tool(
        name="he_log_attempt",
        description="Record a solve attempt for a challenge. Tracks answer, correctness, and notes.",
        inputSchema={
            "type": "object",
            "properties": {
                "challenge_id": {"type": "string"},
                "answer": {"type": "string"},
                "correct": {"type": "boolean"},
                "notes": {"type": "string", "default": ""},
            },
            "required": ["challenge_id", "answer", "correct"],
        },
    ),
    Tool(
        name="he_get_progress",
        description="Return all solve attempts grouped by challenge, with summary of total attempts and solved count.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="he_validate_flag",
        description="Check if a string matches the HackyEaster flag format (he20XX{...}).",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to check for flag format"},
            },
            "required": ["text"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    try:
        result = await _dispatch(name, arguments)
        return result
    except Exception as e:
        return [TextContent(type="text", text=f"Error in {name}: {e}")]


async def _dispatch(name: str, args: dict) -> list[TextContent | ImageContent]:
    if name == "he_discover_challenges":
        dynamic = args.get("dynamic", False)
        challenges = await asyncio.to_thread(discovery.discover_challenges, dynamic=dynamic)
        return [TextContent(type="text", text=json.dumps(challenges, indent=2))]

    if name == "he_fetch_challenge":
        url = args["url"]
        dynamic = args.get("dynamic", False)
        ch = await asyncio.to_thread(discovery.parse_challenge_page, url, dynamic=dynamic)
        return [TextContent(type="text", text=json.dumps(ch, indent=2))]

    if name == "he_fetch_raw":
        url = args["url"]
        dynamic = args.get("dynamic", False)
        result = await asyncio.to_thread(fetch_page, url, dynamic=dynamic)
        payload = {
            "status": result.status,
            "final_url": result.final_url,
            "html_length": len(result.html),
            "html": result.html[:50000],  # cap at 50k to avoid huge responses
            "saved_path": result.saved_path,
        }
        return [TextContent(type="text", text=json.dumps(payload, indent=2))]

    if name == "he_decode":
        text = ctfutils.decode(args["data"], args["encoding"])
        return [TextContent(type="text", text=text)]

    if name == "he_transform":
        params = {}
        if "shift" in args:
            params["shift"] = args["shift"]
        if "key" in args:
            params["key"] = args["key"]
        if "rails" in args:
            params["rails"] = args["rails"]
        if "decrypt" in args:
            params["decrypt"] = args["decrypt"]
        text = ctfutils.transform(args["data"], args["method"], **params)
        return [TextContent(type="text", text=text)]

    if name == "he_analyze_image":
        url = args["url"]
        raw = await asyncio.to_thread(download_bytes, url)

        contents: list[TextContent | ImageContent] = []

        # Return image as base64 for Claude to see
        b64 = base64.b64encode(raw).decode("ascii")
        # Guess mime type
        mime = "image/png"
        if raw[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif raw[:4] == b"\x89PNG":
            mime = "image/png"
        elif raw[:4] == b"GIF8":
            mime = "image/gif"
        elif raw[:4] == b"RIFF":
            mime = "image/webp"

        contents.append(ImageContent(type="image", data=b64, mimeType=mime))

        # Try QR/barcode detection
        qr_results = _try_qr_decode(raw)
        if qr_results:
            contents.append(TextContent(type="text", text=f"QR/Barcode detected: {json.dumps(qr_results)}"))
        else:
            contents.append(TextContent(type="text", text="No QR/barcode detected (pyzbar may not be installed)"))

        return contents

    if name == "he_hash":
        text = ctfutils.compute_hash(args["data"], args.get("algorithm", "sha256"))
        return [TextContent(type="text", text=text)]

    if name == "he_log_attempt":
        entry = state.log_attempt(
            challenge_id=args["challenge_id"],
            answer=args["answer"],
            correct=args["correct"],
            notes=args.get("notes", ""),
        )
        return [TextContent(type="text", text=json.dumps(entry, indent=2))]

    if name == "he_get_progress":
        progress = state.get_progress()
        return [TextContent(type="text", text=json.dumps(progress, indent=2))]

    if name == "he_validate_flag":
        result = ctfutils.validate_flag(args["text"])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _try_qr_decode(image_bytes: bytes) -> list[str]:
    """Attempt QR/barcode detection. Returns decoded strings or empty list."""
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode as zbar_decode

        img = Image.open(io.BytesIO(image_bytes))
        results = zbar_decode(img)
        return [r.data.decode("utf-8", errors="replace") for r in results]
    except ImportError:
        return []
    except Exception:
        return []


def main():
    """Entry point for the MCP server."""
    asyncio.run(_run())


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    main()
