# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python MCP (Model Context Protocol) server that reads continuous glucose monitor (CGM) data from Dexcom sensors via the **unofficial Dexcom Share API**. Designed to integrate with Claude Desktop.

## Setup & Running

```bash
pip install -r requirements.txt
```

Required environment variables:
- `DEXCOM_USERNAME` — Dexcom account email/login (required)
- `DEXCOM_PASSWORD` — Dexcom account password (required)
- `DEXCOM_REGION` — `EU` (default, uses `shareous1.dexcom.com`) or `US` (uses `share2.dexcom.com`)

Run the MCP server directly:
```bash
python server.py
```

## Claude Desktop Integration

Add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "dexcom-cgm": {
      "command": "python",
      "args": ["C:\\Users\\SebastianPokrywka\\AI\\Dexcom\\server.py"],
      "env": {
        "DEXCOM_USERNAME": "...",
        "DEXCOM_PASSWORD": "...",
        "DEXCOM_REGION": "EU"
      }
    }
  }
}
```

## Architecture

Single-file server (`server.py`) with these layers:

1. **`DexcomShareClient`** — async HTTP client wrapping the Dexcom Share REST API. Handles login, session management, and auto-re-login on 500 errors (expired session). Sessions are stored in a module-level singleton (`_client`).

2. **MCP server (`app`)** — built on the `mcp` library, exposes four tools:
   - `get_current_glucose` — latest reading (last 10 min, 1 reading)
   - `get_glucose_history` — readings over 1–24h window
   - `get_glucose_stats` — mean, CV, TIR/TBR/TAR, estimated HbA1c (ADAG formula)
   - `check_alerts` — hypo/hyperglycemia events

3. **Unit conversion** — API always returns `mg/dL`. `mg_to_mmol()` converts for display; `mmol_to_mg()` converts user-supplied thresholds back for comparison.

4. **Date parsing** — Dexcom uses `/Date(milliseconds)/` format; `parse_dexcom_date()` extracts the Unix timestamp.

## Key Constraints

- The Dexcom Share API is **unofficial** and undocumented — it may break after Dexcom app updates.
- `DEXCOM_APPLICATION_ID` is a fixed constant required by the API (`d8665ade-9673-4e27-9ff6-92db4ce13d13`).
- The server communicates over stdio (MCP protocol), not HTTP — it is not a web server.
- All API data is in UTC; timestamps use the `WT` field (wall time) with `ST` as fallback.
- Max history window is 24h / 288 readings (Dexcom Share API limit).
