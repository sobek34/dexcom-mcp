#!/usr/bin/env python3
"""Dexcom CGM MCP Server - odczytuje dane glukozy przez Dexcom Share API."""

import asyncio
import os
import re
import statistics
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Dexcom Share API
DEXCOM_APPLICATION_ID = "d8665ade-9673-4e27-9ff6-92db4ce13d13"
DEXCOM_US_BASE_URL = "https://share2.dexcom.com/ShareWebServices/Services"
DEXCOM_EU_BASE_URL = "https://shareous1.dexcom.com/ShareWebServices/Services"

TREND_ARROWS = {
    0: "→",
    1: "↑↑",
    2: "↑",
    3: "↗",
    4: "→",
    5: "↘",
    6: "↓",
    7: "↓↓",
    8: "?",
    9: "⚠",
}

TREND_NAMES = {
    0: "brak",
    1: "szybko rośnie",
    2: "rośnie",
    3: "lekko rośnie",
    4: "stabilny",
    5: "lekko spada",
    6: "spada",
    7: "szybko spada",
    8: "nie można obliczyć",
    9: "poza zakresem",
}


def parse_dexcom_date(dt_string: str) -> datetime:
    """Parsuje format /Date(timestamp)/ z API Dexcom."""
    match = re.search(r"/Date\((\d+)\)/", dt_string)
    if match:
        ts = int(match.group(1)) / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


def mg_to_mmol(mg_dl: float) -> float:
    """Konwertuje mg/dL na mmol/L."""
    return round(mg_dl / 18.0182, 1)


def mmol_to_mg(mmol_l: float) -> float:
    """Konwertuje mmol/L na mg/dL."""
    return mmol_l * 18.0182


class DexcomShareClient:
    def __init__(self, username: str, password: str, use_eu: bool = True):
        self.username = username
        self.password = password
        self.base_url = DEXCOM_EU_BASE_URL if use_eu else DEXCOM_US_BASE_URL
        self.session_id: str | None = None

    async def login(self) -> str:
        """Loguje się do Dexcom Share API i zwraca session_id."""
        url = f"{self.base_url}/General/LoginPublisherAccountByName"
        payload = {
            "accountName": self.username,
            "password": self.password,
            "applicationId": DEXCOM_APPLICATION_ID,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            # API zwraca string w cudzysłowie: "\"abc123\""
            self.session_id = response.json()
            if isinstance(self.session_id, str):
                self.session_id = self.session_id.strip('"')
            return self.session_id

    async def get_readings(self, minutes: int = 1440, max_count: int = 288) -> list[dict]:
        """Pobiera odczyty glukozy. Automatycznie loguje się jeśli potrzeba."""
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/Publisher/ReadPublisherLatestGlucoseValues"
        params = {
            "sessionId": self.session_id,
            "minutes": minutes,
            "maxCount": max_count,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, timeout=15)

            # Jeśli sesja wygasła, zaloguj ponownie
            if response.status_code == 500:
                await self.login()
                params["sessionId"] = self.session_id
                response = await client.post(url, params=params, timeout=15)

            response.raise_for_status()
            return response.json()


# Globalna instancja klienta
_client: DexcomShareClient | None = None


def get_client() -> DexcomShareClient:
    global _client
    if _client is None:
        username = os.environ.get("DEXCOM_USERNAME", "")
        password = os.environ.get("DEXCOM_PASSWORD", "")
        region = os.environ.get("DEXCOM_REGION", "EU").upper()
        use_eu = region != "US"

        if not username or not password:
            raise ValueError(
                "Brak danych logowania. Ustaw zmienne środowiskowe:\n"
                "  DEXCOM_USERNAME - nazwa konta Dexcom Share\n"
                "  DEXCOM_PASSWORD - hasło do konta\n"
                "  DEXCOM_REGION   - EU (domyślnie) lub US"
            )
        _client = DexcomShareClient(username, password, use_eu)
    return _client


# Serwer MCP
app = Server("dexcom-cgm")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_current_glucose",
            description=(
                "Pobierz aktualny odczyt glukozy z sensora Dexcom CGM. "
                "Zwraca aktualną wartość, trend (strzałkę) oraz status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "enum": ["mg/dL", "mmol/L"],
                        "default": "mmol/L",
                        "description": "Jednostka pomiaru glukozy",
                    }
                },
            },
        ),
        types.Tool(
            name="get_glucose_history",
            description=(
                "Pobierz historię odczytów glukozy z ostatnich X godzin (maks. 24h). "
                "Odczyty co 5 minut."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 24,
                        "description": "Liczba ostatnich godzin (1–24)",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["mg/dL", "mmol/L"],
                        "default": "mmol/L",
                        "description": "Jednostka pomiaru glukozy",
                    },
                },
            },
        ),
        types.Tool(
            name="get_glucose_stats",
            description=(
                "Oblicz statystyki glukozy: średnią, TIR (Time in Range), "
                "TBR (Time Below Range), TAR (Time Above Range) oraz szacowany HbA1c."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 24,
                        "description": "Zakres czasowy dla statystyk w godzinach (maks. 24h)",
                    },
                    "low_threshold": {
                        "type": "number",
                        "default": 3.9,
                        "description": "Dolna granica TIR w mmol/L (domyślnie 3.9 = 70 mg/dL)",
                    },
                    "high_threshold": {
                        "type": "number",
                        "default": 10.0,
                        "description": "Górna granica TIR w mmol/L (domyślnie 10.0 = 180 mg/dL)",
                    },
                },
            },
        ),
        types.Tool(
            name="check_alerts",
            description=(
                "Sprawdź zdarzenia hipoglikemii i hiperglikemii z ostatnich godzin. "
                "Zwraca listę odczytów poniżej/powyżej zadanych progów."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 24,
                        "description": "Zakres czasowy w godzinach",
                    },
                    "low_alert": {
                        "type": "number",
                        "default": 3.9,
                        "description": "Próg hipoglikemii w mmol/L (domyślnie 3.9)",
                    },
                    "high_alert": {
                        "type": "number",
                        "default": 10.0,
                        "description": "Próg hiperglikemii w mmol/L (domyślnie 10.0)",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        client = get_client()

        if name == "get_current_glucose":
            unit = arguments.get("unit", "mmol/L")
            readings = await client.get_readings(minutes=10, max_count=1)

            if not readings:
                return [types.TextContent(type="text", text="Brak odczytow z sensora.")]

            r = readings[0]
            value_mg = r["Value"]
            trend = r.get("Trend", 4)
            dt = parse_dexcom_date(r.get("WT", r.get("ST", "")))
            time_str = dt.strftime("%H:%M UTC")
            arrow = TREND_ARROWS.get(trend, "→")
            trend_name = TREND_NAMES.get(trend, "nieznany")

            mmol = mg_to_mmol(value_mg)
            if mmol < 3.9:
                status = "HIPOGLYKEMIA"
            elif mmol > 10.0:
                status = "HIPERGLIKEMIA"
            else:
                status = "W NORMIE"

            if unit == "mmol/L":
                display_val = f"{mmol} mmol/L"
            else:
                display_val = f"{value_mg} mg/dL"

            return [
                types.TextContent(
                    type="text",
                    text=(
                        f"Glukoza: {display_val} {arrow}\n"
                        f"Trend: {trend_name}\n"
                        f"Status: {status}\n"
                        f"Czas odczytu: {time_str}"
                    ),
                )
            ]

        elif name == "get_glucose_history":
            hours = min(max(arguments.get("hours", 3), 1), 24)
            unit = arguments.get("unit", "mmol/L")
            minutes = hours * 60
            max_count = hours * 12 + 5

            readings = await client.get_readings(minutes=minutes, max_count=max_count)

            if not readings:
                return [types.TextContent(type="text", text="Brak danych historycznych.")]

            lines = [f"Historia glukozy — ostatnie {hours}h ({len(readings)} odczytow):\n"]

            for r in reversed(readings):
                value_mg = r["Value"]
                trend = r.get("Trend", 4)
                dt = parse_dexcom_date(r.get("WT", r.get("ST", "")))
                time_str = dt.strftime("%H:%M")
                arrow = TREND_ARROWS.get(trend, "→")

                if unit == "mmol/L":
                    val = mg_to_mmol(value_mg)
                    unit_str = "mmol/L"
                else:
                    val = value_mg
                    unit_str = "mg/dL"

                lines.append(f"{time_str} UTC: {val} {unit_str} {arrow}")

            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "get_glucose_stats":
            hours = min(max(arguments.get("hours", 24), 1), 24)
            low_threshold = arguments.get("low_threshold", 3.9)
            high_threshold = arguments.get("high_threshold", 10.0)
            low_mg = mmol_to_mg(low_threshold)
            high_mg = mmol_to_mg(high_threshold)

            readings = await client.get_readings(
                minutes=hours * 60, max_count=hours * 12 + 5
            )

            if not readings:
                return [types.TextContent(type="text", text="Brak danych do obliczen.")]

            values = [r["Value"] for r in readings]
            n = len(values)
            avg_mg = statistics.mean(values)
            avg_mmol = mg_to_mmol(avg_mg)

            in_range = sum(1 for v in values if low_mg <= v <= high_mg)
            below = sum(1 for v in values if v < low_mg)
            above = sum(1 for v in values if v > high_mg)

            tir = round(in_range / n * 100, 1)
            tbr = round(below / n * 100, 1)
            tar = round(above / n * 100, 1)

            # Szacowany HbA1c wg wzoru ADAG (mg/dL)
            estimated_a1c = round((avg_mg + 46.7) / 28.7, 1)

            std_mg = statistics.stdev(values) if n > 1 else 0.0
            cv = round((std_mg / avg_mg) * 100, 1) if avg_mg > 0 else 0.0

            return [
                types.TextContent(
                    type="text",
                    text=(
                        f"Statystyki glukozy — ostatnie {hours}h ({n} odczytow):\n\n"
                        f"Srednia:          {avg_mmol} mmol/L ({round(avg_mg)} mg/dL)\n"
                        f"Odchylenie std:   {mg_to_mmol(std_mg)} mmol/L\n"
                        f"CV:               {cv}%\n\n"
                        f"TIR ({low_threshold}–{high_threshold} mmol/L):  {tir}%\n"
                        f"TBR (<{low_threshold} mmol/L):         {tbr}%\n"
                        f"TAR (>{high_threshold} mmol/L):        {tar}%\n\n"
                        f"Szacowany HbA1c:  {estimated_a1c}%"
                    ),
                )
            ]

        elif name == "check_alerts":
            hours = min(max(arguments.get("hours", 24), 1), 24)
            low_alert = arguments.get("low_alert", 3.9)
            high_alert = arguments.get("high_alert", 10.0)
            low_mg = mmol_to_mg(low_alert)
            high_mg = mmol_to_mg(high_alert)

            readings = await client.get_readings(
                minutes=hours * 60, max_count=hours * 12 + 5
            )

            if not readings:
                return [types.TextContent(type="text", text="Brak danych do sprawdzenia alertow.")]

            low_events: list[str] = []
            high_events: list[str] = []

            for r in reversed(readings):
                value_mg = r["Value"]
                dt = parse_dexcom_date(r.get("WT", r.get("ST", "")))
                time_str = dt.strftime("%H:%M")
                val_mmol = mg_to_mmol(value_mg)

                if value_mg < low_mg:
                    low_events.append(f"  {time_str} UTC: {val_mmol} mmol/L")
                elif value_mg > high_mg:
                    high_events.append(f"  {time_str} UTC: {val_mmol} mmol/L")

            lines = [f"Alerty glukozy — ostatnie {hours}h:\n"]

            if low_events:
                lines.append(f"HIPOGLYKEMIE — {len(low_events)} odczytow ponizej {low_alert} mmol/L:")
                lines.extend(low_events[:10])
                if len(low_events) > 10:
                    lines.append(f"  ... i {len(low_events) - 10} wiecej")
            else:
                lines.append(f"Brak hipoglykemii (<{low_alert} mmol/L)")

            lines.append("")

            if high_events:
                lines.append(f"HIPERGLIKEMIE — {len(high_events)} odczytow powyzej {high_alert} mmol/L:")
                lines.extend(high_events[:10])
                if len(high_events) > 10:
                    lines.append(f"  ... i {len(high_events) - 10} wiecej")
            else:
                lines.append(f"Brak hiperglikemii (>{high_alert} mmol/L)")

            return [types.TextContent(type="text", text="\n".join(lines))]

        else:
            return [types.TextContent(type="text", text=f"Nieznane narzedzie: {name}")]

    except ValueError as e:
        return [types.TextContent(type="text", text=f"Blad konfiguracji: {e}")]
    except httpx.HTTPStatusError as e:
        return [
            types.TextContent(
                type="text",
                text=f"Blad API Dexcom ({e.response.status_code}): {e.response.text[:200]}",
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Blad: {type(e).__name__}: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
