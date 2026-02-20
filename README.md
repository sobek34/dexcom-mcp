# Dexcom CGM MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that reads real-time continuous glucose monitor (CGM) data from Dexcom sensors via the **Dexcom Share API**. Integrates with Claude Desktop, allowing Claude to read your glucose levels, trends, and statistics directly.

Supports **Dexcom One, G6, G7** — both EU and US regions.

---

## Requirements

- Python 3.10+
- A Dexcom account with **Share** enabled in the mobile app
- An active CGM sensor

## Installation

### Option A — run directly from GitHub with `uvx` (no install needed)

```bash
uvx --from git+https://github.com/sobek34/dexcom-mcp.git dexcom-mcp
```

### Option B — install with pip

```bash
pip install git+https://github.com/sobek34/dexcom-mcp.git
dexcom-mcp
```

### Option C — clone and run locally

```bash
git clone https://github.com/sobek34/dexcom-mcp.git
cd dexcom-mcp
pip install -r requirements.txt
python server.py
```

---

## Configuration

Set these environment variables before running:

| Variable           | Description                              | Default    |
|--------------------|------------------------------------------|------------|
| `DEXCOM_USERNAME`  | Dexcom account email / login             | *required* |
| `DEXCOM_PASSWORD`  | Dexcom account password                  | *required* |
| `DEXCOM_REGION`    | `EU` (Europe) or `US`                    | `EU`       |

> **Note:** Dexcom One uses the EU server (`shareous1.dexcom.com`).
> Dexcom G6/G7 in the US uses the US server (`share2.dexcom.com`).

---

## Claude Desktop Integration

Add to `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

### With uvx (recommended — always uses latest version)

```json
{
  "mcpServers": {
    "dexcom-cgm": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/sobek34/dexcom-mcp.git", "dexcom-mcp"],
      "env": {
        "DEXCOM_USERNAME": "your@email.com",
        "DEXCOM_PASSWORD": "your_password",
        "DEXCOM_REGION": "EU"
      }
    }
  }
}
```

### With a local clone

```json
{
  "mcpServers": {
    "dexcom-cgm": {
      "command": "python",
      "args": ["/path/to/dexcom-mcp/server.py"],
      "env": {
        "DEXCOM_USERNAME": "your@email.com",
        "DEXCOM_PASSWORD": "your_password",
        "DEXCOM_REGION": "EU"
      }
    }
  }
}
```

---

## Available MCP Tools

### `get_current_glucose`
Returns the latest glucose reading, trend arrow, and status.

**Parameters:**
- `unit` — `"mmol/L"` (default) or `"mg/dL"`

**Example output:**
```
Glucose: 5.8 mmol/L →
Trend: stable
Status: IN RANGE
Reading time: 14:35 UTC
```

---

### `get_glucose_history`
Returns readings for the last X hours (up to 24h), one every 5 minutes.

**Parameters:**
- `hours` — 1–24 (default: 3)
- `unit` — `"mmol/L"` or `"mg/dL"`

---

### `get_glucose_stats`
Calculates statistics over a time window.

**Parameters:**
- `hours` — 1–24 (default: 24)
- `low_threshold` — lower TIR boundary in mmol/L (default: 3.9)
- `high_threshold` — upper TIR boundary in mmol/L (default: 10.0)

**Returns:** mean, standard deviation, CV, TIR / TBR / TAR, estimated HbA1c (ADAG formula)

---

### `check_alerts`
Lists hypoglycemia and hyperglycemia events within a time window.

**Parameters:**
- `hours` — 1–24 (default: 24)
- `low_alert` — hypo threshold in mmol/L (default: 3.9)
- `high_alert` — hyper threshold in mmol/L (default: 10.0)

---

## How to Enable Dexcom Share

1. Open the **Dexcom** app (One / G6 / G7) on your phone
2. Go to **Settings → Share** and enable sharing
3. You do **not** need to add a follower — just enabling Share is enough

---

## Security

- Never hardcode credentials — always use environment variables
- This uses an **unofficial, undocumented API** — it may break after Dexcom app updates

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Dexcom, Inc. Use at your own risk. Do not make medical decisions based solely on data returned by this tool.
