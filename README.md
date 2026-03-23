# HackyEaster Solver

MCP server for Claude-driven [HackyEaster](https://www.hackyeaster.com/) CTF solving. Uses [Scrapling](https://github.com/D4Vinci/Scrapling) for page fetching and exposes CTF utility tools so Claude can reason through challenges, submit answers via Playwright, and iterate.

## Setup

### Quick install (no clone needed)

Add to your `~/.mcp.json`:

```json
{
  "mcpServers": {
    "hackyeaster": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/cloudwarriors-ai/hackyeaster-solver", "hackyeaster-mcp"]
    }
  }
}
```

Restart Claude Code. The `he_*` tools will appear in the MCP servers panel.

### Local development

If you want to modify the server or keep persistent state in a known location:

```bash
git clone https://github.com/cloudwarriors-ai/hackyeaster-solver.git
cd hackyeaster-solver
uv sync
```

Then in `~/.mcp.json`, point at your local clone:

```json
{
  "mcpServers": {
    "hackyeaster": {
      "command": "bash",
      "args": ["-c", "uv run --directory /path/to/hackyeaster-solver python -m hackyeaster_mcp.server"]
    }
  }
}
```

## Tools

### Scraping
| Tool | Description |
|------|-------------|
| `he_discover_challenges` | Scrape hackyeaster.com and return available challenges |
| `he_fetch_challenge` | Fetch and parse a specific challenge page |
| `he_fetch_raw` | Fetch any URL and return raw HTML |

### CTF Utilities
| Tool | Description |
|------|-------------|
| `he_decode` | Decode: base64, hex, url, binary, morse, decimal, octal, base32 |
| `he_transform` | Transform: caesar, rot13, swap_pairs, reverse, rail_fence, vigenere, xor, atbash |
| `he_analyze_image` | Download image for visual analysis + QR/barcode detection |
| `he_hash` | Compute hashes: md5, sha1, sha256, sha512 |

### State
| Tool | Description |
|------|-------------|
| `he_log_attempt` | Record a solve attempt |
| `he_get_progress` | View all attempts and solved challenges |
| `he_validate_flag` | Check if text matches flag format `he20XX{...}` |

## How It Works

Claude is the solver. The MCP server provides the tools; Claude provides the reasoning.

1. `he_discover_challenges` — scrape the site for challenges
2. `he_fetch_challenge` — read challenge content, hints, embedded data
3. Claude reasons about the puzzle, calls `he_decode` / `he_transform` / `he_analyze_image` as needed
4. Playwright MCP (separate, already available in Claude Code) handles form interaction and answer submission
5. `he_log_attempt` tracks what was tried and what worked

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Claude Code with MCP support
- Playwright MCP server (for answer submission when challenges go live)

## Architecture

```
Claude (solver brain)
  |
  +-- hackyeaster MCP -- Scrapling fetch + CTF utils + state
  |
  +-- playwright MCP --- form interaction, submit answers, screenshots
```
