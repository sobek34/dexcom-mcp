# Dexcom CGM MCP Server

Serwer MCP odczytujący dane z glukometru ciągłego Dexcom (Dexcom One, G6, G7)
przez **Dexcom Share API**.

## Wymagania

- Python 3.11+
- Konto Dexcom z włączoną funkcją **Share** w aplikacji mobilnej
- Aktywny sensor CGM

## Instalacja

```bash
cd C:\Users\SebastianPokrywka\AI\Dexcom
pip install -r requirements.txt
```

## Konfiguracja

Ustaw zmienne środowiskowe przed uruchomieniem:

| Zmienna           | Opis                                      | Domyślnie |
|-------------------|-------------------------------------------|-----------|
| `DEXCOM_USERNAME` | Nazwa konta Dexcom (e-mail lub login)     | wymagane  |
| `DEXCOM_PASSWORD` | Hasło do konta Dexcom                     | wymagane  |
| `DEXCOM_REGION`   | Region serwera: `EU` (Europa) lub `US`    | `EU`      |

> **Uwaga:** Dexcom One używa serwera EU (`shareous1.dexcom.com`).
> Dexcom G6/G7 w USA używa serwera US (`share2.dexcom.com`).

## Konfiguracja w Claude Desktop

Dodaj do pliku `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dexcom-cgm": {
      "command": "python",
      "args": ["C:\\Users\\SebastianPokrywka\\AI\\Dexcom\\server.py"],
      "env": {
        "DEXCOM_USERNAME": "twoj@email.com",
        "DEXCOM_PASSWORD": "twoje_haslo",
        "DEXCOM_REGION": "EU"
      }
    }
  }
}
```

## Dostępne narzędzia MCP

### `get_current_glucose`
Pobiera aktualny odczyt glukozy.

**Parametry:**
- `unit` — `"mmol/L"` (domyślnie) lub `"mg/dL"`

**Przykład odpowiedzi:**
```
Glukoza: 5.8 mmol/L →
Trend: stabilny
Status: W NORMIE
Czas odczytu: 14:35 UTC
```

---

### `get_glucose_history`
Pobiera historię odczytów z ostatnich X godzin.

**Parametry:**
- `hours` — liczba godzin 1–24 (domyślnie 3)
- `unit` — `"mmol/L"` lub `"mg/dL"`

---

### `get_glucose_stats`
Oblicza statystyki glukozy.

**Parametry:**
- `hours` — zakres czasowy 1–24h (domyślnie 24)
- `low_threshold` — dolna granica TIR w mmol/L (domyślnie 3.9)
- `high_threshold` — górna granica TIR w mmol/L (domyślnie 10.0)

**Zwraca:** średnią, CV, TIR/TBR/TAR, szacowany HbA1c

---

### `check_alerts`
Sprawdza zdarzenia hipoglikemii i hiperglikemii.

**Parametry:**
- `hours` — zakres czasowy 1–24h (domyślnie 24)
- `low_alert` — próg hipoglikemii w mmol/L (domyślnie 3.9)
- `high_alert` — próg hiperglikemii w mmol/L (domyślnie 10.0)

## Jak włączyć Dexcom Share

1. Otwórz aplikację **Dexcom One** (lub G6/G7) na telefonie
2. Przejdź do ustawień → **Share** → włącz udostępnianie
3. Nie musisz dodawać obserwatora — wystarczy włączona funkcja Share

## Bezpieczeństwo

- Nigdy nie wpisuj hasła bezpośrednio w pliku — używaj zmiennych środowiskowych
- To jest **nieoficjalne API** — może przestać działać po aktualizacji Dexcom
