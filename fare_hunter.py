import json
import os
import re
import time
import requests

# =====================================================================
#                        KONFIGURACJA TRAS
# =====================================================================
DATES_GLIWICE_DOMARADZ = [
    "11.09.2026",
    "16.09.2026",
    "17.09.2026",
    "25.09.2026",
    "02.10.2026",
    "09.10.2026",
    "16.10.2026",
    "23.10.2026",
    "30.10.2026",
    "06.11.2026",
    "10.11.2026",
    "13.11.2026",
    "20.11.2026",
]

DATES_DOMARADZ_GLIWICE = [
    "13.09.2026",
    "20.09.2026",
    "27.09.2026",
    "04.10.2026",
    "11.10.2026",
    "18.10.2026",
    "25.10.2026",
    "02.11.2026",
    "08.11.2026",
    "15.11.2026",
    "22.11.2026",
]

TARGET_MAX_PRICE = 45.00
TICKET_TYPE = "normal"  # 'student' lub 'normal'

# Pobieranie webhooka z sejfu GitHub Secrets
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

STOPS = {
    "gliwice": {
        "id": "123",
        "name": "GLIWICE Centrum Przesiadkowe ul. Składowa 8a",
    },
    "domaradz": {"id": "47", "name": "DOMARADZ "},
}


def send_discord_alert(cheap_tickets: list):
    """Wysyła powiadomienie na Discorda z dzieleniem wiadomości na paczki < 2000 znaków."""
    if not DISCORD_WEBHOOK_URL:
        print("[!] Brak zmiennej DISCORD_WEBHOOK_URL!")
        return

    count = len(cheap_tickets)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    header_text = (
        f"🔥 **ZNALEZIONO TANIE BILETY NEOBUS ({count} szt.)!** @everyone\n"
    )
    footer_text = "\n🛒 **Kup bilet:** https://neobus.pl/"

    ticket_blocks = []
    for t in cheap_tickets:
        ticket_blocks.append(
            f"📍 **{t.get('route')}** ({t.get('date')})\n"
            f"   ⏰ Kurs: **{t.get('hours')}** | 💰 Cena: **{t.get('price'):.2f} PLN**\n"
        )

    messages = []
    curr = header_text
    for b in ticket_blocks:
        if len(curr) + len(b) + len(footer_text) > 1800:
            messages.append(curr + footer_text)
            curr = header_text + b
        else:
            curr += b
    if curr:
        messages.append(curr + footer_text)

    for msg in messages:
        try:
            r = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"username": "Neobus Tracker", "content": msg},
                headers=headers,
                timeout=10,
            )
            if r.status_code in [200, 204]:
                print("✅ Wysłano powiadomienie na Discord!")
            else:
                print(f"[!] Błąd Discord ({r.status_code}): {r.text}")
            time.sleep(0.5)
        except Exception as e:
            print(f"[!] Błąd połączenia z Discordem: {e}")


def get_courses(
    from_id: str, from_name: str, to_id: str, to_name: str, date_str: str
):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://neobus.pl",
        "Referer": "https://neobus.pl/",
    }
    session.get("https://neobus.pl/", headers=headers, timeout=10)

    payload = {
        "ajax": "true",
        "dataType": "json",
        "module": "neotickets",
        "step": "1",
        "ticket_type": TICKET_TYPE,
        "initial_stop": from_id,
        "final_stop": to_id,
        "passengers": "1",
        "date_there": date_str,
        "date_return": "",
        "initial_stop_name": from_name,
        "final_stop_name": to_name,
    }

    resp = session.post(
        "https://neobus.pl/", data=payload, headers=headers, timeout=15
    )
    raw = resp.json() if resp.status_code == 200 else {}

    if isinstance(raw, dict) and "neotickets" in raw:
        content = raw["neotickets"]
        data = json.loads(content) if isinstance(content, str) else content
    else:
        data = raw

    courses = []
    if "ga4_data" in data and len(data["ga4_data"]) > 0:
        for it in data["ga4_data"][0].get("items", []):
            name = it.get("item_name", "")
            price = it.get("price") or it.get("discount", 0.0)
            try:
                price = float(price)
            except Exception:
                price = 0.0

            match = re.search(
                r"(\d{2}-\d{2})\s*-\s*(\d{2}:\d{2}|\d{2}-\d{2})", name
            )
            hours_str = (
                f"{match.group(1).replace('-', ':')} -> {match.group(2).replace('-', ':')}"
                if match
                else "Standardowy"
            )

            courses.append({"hours": hours_str, "price": price})
    return courses


def check_route(route_label: str, from_id: str, to_id: str, dates_list: list):
    print(f"\n🚌 TRASA: {route_label}")
    cheap_found = []

    for d in dates_list:
        courses = get_courses(
            from_id,
            STOPS["gliwice"]["name"]
            if from_id == "123"
            else STOPS["domaradz"]["name"],
            to_id,
            STOPS["domaradz"]["name"]
            if to_id == "47"
            else STOPS["gliwice"]["name"],
            d,
        )

        for c in courses:
            print(f"  [{d}] {c['hours']} -> {c['price']:.2f} PLN")
            if 0 < c["price"] <= TARGET_MAX_PRICE:
                cheap_found.append(
                    {
                        "route": route_label,
                        "date": d,
                        "hours": c["hours"],
                        "price": c["price"],
                    }
                )
        time.sleep(1.5)

    return cheap_found


def main():
    print("=== SPRAWDZANIE KURSÓW NEOBUS W GITHUB ACTIONS ===")
    all_cheap = []

    if DATES_GLIWICE_DOMARADZ:
        all_cheap.extend(
            check_route(
                "Gliwice -> Domaradz",
                STOPS["gliwice"]["id"],
                STOPS["domaradz"]["id"],
                DATES_GLIWICE_DOMARADZ,
            )
        )

    if DATES_DOMARADZ_GLIWICE:
        all_cheap.extend(
            check_route(
                "Domaradz -> Gliwice",
                STOPS["domaradz"]["id"],
                STOPS["gliwice"]["id"],
                DATES_DOMARADZ_GLIWICE,
            )
        )

    if all_cheap:
        print(f"\n🚨 Znaleziono {len(all_cheap)} tanich biletów! Wysyłam alert...")
        send_discord_alert(all_cheap)
    else:
        print(f"\n[i] Brak biletów w cenie <= {TARGET_MAX_PRICE:.2f} PLN.")


if __name__ == "__main__":
    main()
