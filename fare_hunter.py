import csv
from datetime import date, timedelta
import json
import os
import re
import time
import requests

# =====================================================================
#                        KONFIGURACJA
# =====================================================================

# 1. DNI, NA KTÓRE CHCESZ OTRZYMAĆ POWIADOMIENIE O TANIM BILECIE
MY_TRIP_DATES_GLIWICE_DOMARADZ = [
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

MY_TRIP_DATES_DOMARADZ_GLIWICE = [
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

TARGET_MAX_PRICE = 45.00  # Próg promocji
TICKET_TYPE = "normal"  # 'student' lub 'normal'
DAYS_FORWARD_SEARCH = 120  # Ile dni w przód zbierać dane do historii CSV

CSV_GLIWICE_DOMARADZ = "ceny_gliwice_domaradz.csv"
CSV_DOMARADZ_GLIWICE = "ceny_domaradz_gliwice.csv"
LATEST_DATE_FILE = "ostatnia_data_sprzedazy.txt"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

STOPS = {
    "gliwice": {
        "id": "123",
        "name": "GLIWICE Centrum Przesiadkowe ul. Składowa 8a",
    },
    "domaradz": {"id": "47", "name": "DOMARADZ "},
}


# =====================================================================
#                   DYNAMIKA DAT I ZAPIS
# =====================================================================


def generate_dynamic_dates(days_count: int) -> list:
    today = date.today()
    return [
        (today + timedelta(days=i)).strftime("%d.%m.%Y")
        for i in range(days_count)
    ]


def save_route_to_csv(courses_list: list, csv_filename: str):
    """Zapisuje kursy do dedykowanego pliku CSV (zabezpieczenie przed duplikatami)."""
    if not courses_list:
        return

    file_exists = os.path.isfile(csv_filename)
    last_prices = {}

    if file_exists:
        try:
            with open(csv_filename, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("Data kursu"), row.get("Godzina kursu"))
                    try:
                        last_prices[key] = float(row.get("Cena (PLN)", 0))
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"[!] Błąd odczytu {csv_filename}: {e}")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    records_to_add = []

    for c in courses_list:
        key = (c["date"], c["hours"])
        prev = last_prices.get(key)
        if prev is None or abs(c["price"] - prev) > 0.01:
            records_to_add.append([
                timestamp,
                c["date"],
                c["hours"],
                f"{c['price']:.2f}",
            ])

    if records_to_add:
        with open(csv_filename, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Data sprawdzenia",
                    "Data kursu",
                    "Godzina kursu",
                    "Cena (PLN)",
                ])
            writer.writerows(records_to_add)
        print(
            f"💾 [{csv_filename}] Zapisano {len(records_to_add)} nowych/zmienionych cen."
        )
    else:
        print(f"⚡ [{csv_filename}] Brak zmian w cenach.")


# =====================================================================
#                   POWIADOMIENIA DISCORD
# =====================================================================


def send_discord_message(content: str):
    if not DISCORD_WEBHOOK_URL:
        return
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"username": "Neobus Sentinel", "content": content},
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"[!] Błąd Discord: {e}")


def send_discord_alert(cheap_tickets: list):
    """Wysyła alert o tanich biletach na Twoje zaplanowane wyjazdy."""
    if not DISCORD_WEBHOOK_URL or not cheap_tickets:
        return

    count = len(cheap_tickets)
    header = f"🔥 **ZNALEZIONO TANIE BILETY NA TWOJE TERMINY ({count} szt.)!** @everyone\n"
    footer = "\n🛒 **Kup bilet:** https://neobus.pl/"

    blocks = [
        f"📍 **{t['route']}** ({t['date']})\n   ⏰ Kurs: **{t['hours']}** | 💰 Cena: **{t['price']:.2f} PLN**\n"
        for t in cheap_tickets
    ]

    messages, curr = [], header
    for b in blocks:
        if len(curr) + len(b) + len(footer) > 1800:
            messages.append(curr + footer)
            curr = header + b
        else:
            curr += b
    if curr:
        messages.append(curr + footer)

    for msg in messages:
        send_discord_message(msg)
        time.sleep(0.5)


def check_and_notify_new_schedule(active_dates: list):
    """Wysyła alert, jeśli pojawi się zupełnie nowy miesiąc/termin w sprzedaży."""
    if not active_dates:
        return

    dt_dates = sorted([time.strptime(d, "%d.%m.%Y") for d in active_dates])
    furthest = time.strftime("%d.%m.%Y", dt_dates[-1])

    prev = ""
    if os.path.isfile(LATEST_DATE_FILE):
        with open(LATEST_DATE_FILE, "r", encoding="utf-8") as f:
            prev = f.read().strip()

    if not prev:
        with open(LATEST_DATE_FILE, "w", encoding="utf-8") as f:
            f.write(furthest)
        return

    if time.strptime(furthest, "%d.%m.%Y") > time.strptime(prev, "%d.%m.%Y"):
        msg = (
            f"📢 **NEOBUS OTWORZYŁ NOWĄ PULĘ BILETÓW!** @everyone\n\n"
            f"📅 Sprzedaż wydłużona do: **{furthest}** (poprzednio: {prev})\n"
            f"🚀 https://neobus.pl/"
        )
        send_discord_message(msg)
        with open(LATEST_DATE_FILE, "w", encoding="utf-8") as f:
            f.write(furthest)


# =====================================================================
#                        LOGIKA API NEOBUS
# =====================================================================


def get_courses(from_id: str, from_name: str, to_id: str, to_name: str, date_str: str):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://neobus.pl",
        "Referer": "https://neobus.pl/",
    }
    try:
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
        resp = session.post("https://neobus.pl/", data=payload, headers=headers, timeout=15)
        raw = resp.json() if resp.status_code == 200 else {}
    except Exception:
        return []

    content = raw.get("neotickets", raw) if isinstance(raw, dict) else raw
    data = json.loads(content) if isinstance(content, str) else content

    # Szukanie liczby wolnych miejsc w surowej zawartości HTML modułu
    html_text = str(raw)

    courses = []
    if isinstance(data, dict) and "ga4_data" in data and len(data["ga4_data"]) > 0:
        for it in data["ga4_data"][0].get("items", []):
            name = it.get("item_name", "")
            price = it.get("price") or it.get("discount", 0.0)
            try:
                price = float(price)
            except Exception:
                price = 0.0

            match_hours = re.search(r"(\d{2}-\d{2})\s*-\s*(\d{2}:\d{2}|\d{2}-\d{2})", name)
            hours_str = (
                f"{match_hours.group(1).replace('-', ':')} -> {match_hours.group(2).replace('-', ':')}"
                if match_hours
                else "Standardowy"
            )

            # Szukanie wolnych foteli dla danego kursu w atrybutach (np. "Wolnych miejsc: 14" lub data-seats="14")
            seats_match = re.search(r"(?:wolnych|miejsc|seats)[^\d]*(\d+)", html_text, re.IGNORECASE)
            seats_count = int(seats_match.group(1)) if seats_match else "B/D"

            if price > 0:
                courses.append({
                    "hours": hours_str,
                    "price": price,
                    "seats": seats_count
                })
    return courses


def check_route(route_label: str, from_id: str, to_id: str, dates_list: list):
    print(f"🚌 Sprawdzam trasę: {route_label}...")
    courses = []
    empty_days = 0

    for d in dates_list:
        found = get_courses(
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
        if found:
            empty_days = 0
            for c in found:
                courses.append({
                    "route": route_label,
                    "date": d,
                    "hours": c["hours"],
                    "price": c["price"],
                })
        else:
            empty_days += 1

        if empty_days >= 6:
            print(
                f"🛑 [Koniec puli] Brak biletów od {d}. Przerywam skanowanie trasy."
            )
            break

        time.sleep(0.3)

    return courses


# =====================================================================
#                           GŁÓWNY PROGRAM
# =====================================================================


def main():
    print("=== MONITORING NEOBUS (ARCHIWUM WSZYSTKICH DNI + ALERT CELOWANY) ===")
    dates = generate_dynamic_dates(DAYS_FORWARD_SEARCH)

    # 1. Trasa: Gliwice -> Domaradz
    courses_gli_dom = check_route(
        "Gliwice -> Domaradz",
        STOPS["gliwice"]["id"],
        STOPS["domaradz"]["id"],
        dates,
    )
    save_route_to_csv(courses_gli_dom, CSV_GLIWICE_DOMARADZ)

    # 2. Trasa: Domaradz -> Gliwice
    courses_dom_gli = check_route(
        "Domaradz -> Gliwice",
        STOPS["domaradz"]["id"],
        STOPS["gliwice"]["id"],
        dates,
    )
    save_route_to_csv(courses_dom_gli, CSV_DOMARADZ_GLIWICE)

    # 3. Wykrywanie nowej puli terminów na kolejne miesiące
    all_active_dates = list(
        {c["date"] for c in (courses_gli_dom + courses_dom_gli)}
    )
    check_and_notify_new_schedule(all_active_dates)

    # 4. Filtrowanie okazji TYLKO na Twoje wybrane dni podróży
    my_cheap_tickets = []

    for c in courses_gli_dom:
        if (
            0 < c["price"] <= TARGET_MAX_PRICE
            and c["date"] in MY_TRIP_DATES_GLIWICE_DOMARADZ
        ):
            my_cheap_tickets.append(c)

    for c in courses_dom_gli:
        if (
            0 < c["price"] <= TARGET_MAX_PRICE
            and c["date"] in MY_TRIP_DATES_DOMARADZ_GLIWICE
        ):
            my_cheap_tickets.append(c)

    # 5. Wysłanie powiadomienia
    if my_cheap_tickets:
        print(
            f"🚨 Znaleziono {len(my_cheap_tickets)} biletów promocyjnych na Twoje terminy!"
        )
        send_discord_alert(my_cheap_tickets)
    else:
        print(
            f"[i] Brak tanich biletów (<= {TARGET_MAX_PRICE:.2f} PLN) na Twoje zaplanowane wyjazdy."
        )


if __name__ == "__main__":
    main()
