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

# 1. DNI, NA KTÓRE CHCESZ OTRZYMAĆ POWIADOMIENIE NA DISCORDZIE
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

TARGET_MAX_PRICE = 60.00  # Próg promocyjny (PLN)
TICKET_TYPE = "normal"    # 'student' lub 'normal'
DAYS_FORWARD_SEARCH = 120 # Zakres poszukiwań w przód

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
#                   DYNAMIKA DAT I BAZA CSV
# =====================================================================


def generate_dynamic_dates(days_count: int) -> list:
    today = date.today()
    return [
        (today + timedelta(days=i)).strftime("%d.%m.%Y")
        for i in range(days_count)
    ]


def save_route_to_csv(courses_list: list, csv_filename: str):
    """Zapisuje kursy do dedykowanego pliku CSV (z ceną oraz zbadaną liczbą miejsc)."""
    if not courses_list:
        return

    file_exists = os.path.isfile(csv_filename)
    last_records = {}

    if file_exists:
        try:
            with open(csv_filename, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("Data kursu"), row.get("Godzina kursu"))
                    try:
                        price = float(row.get("Cena (PLN)", 0))
                        seats = row.get("Wolne miejsca", "B/D")
                        last_records[key] = (price, seats)
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"[!] Błąd odczytu {csv_filename}: {e}")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    records_to_add = []

    for c in courses_list:
        key = (c["date"], c["hours"])
        prev = last_records.get(key)
        curr_seats_str = str(c.get("seats", "B/D"))

        is_new = prev is None
        price_changed = prev and abs(c["price"] - prev[0]) > 0.01
        seats_changed = prev and str(prev[1]) != curr_seats_str and curr_seats_str != "B/D"

        if is_new or price_changed or seats_changed:
            records_to_add.append([
                timestamp,
                c["date"],
                c["hours"],
                f"{c['price']:.2f}",
                curr_seats_str,
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
                    "Wolne miejsca",
                ])
            writer.writerows(records_to_add)
        print(f"💾 [{csv_filename}] Zapisano/zaktualizowano {len(records_to_add)} rekordów.")
    else:
        print(f"⚡ [{csv_filename}] Ceny i stan miejsc bez zmian.")


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
    """Wysyła alert o tanich biletach z dokładną liczbą wolnych miejsc."""
    if not DISCORD_WEBHOOK_URL or not cheap_tickets:
        return

    count = len(cheap_tickets)
    header = (
        f"🔥 **ZNALEZIONO TANIE BILETY NA TWOJE TERMINY ({count} szt.)!**"
        " @everyone\n"
    )

    blocks = []
    for t in cheap_tickets:
        seats_str = f"{t.get('seats')} szt." if isinstance(t.get('seats'), int) else "Dostępne"
        block = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 **{t['route']}** | 📅 **{t['date']}**\n"
            f"⏰ Godzina: **{t['hours']}**\n"
            f"💰 Cena: **{t['price']:.2f} PLN** | 💺 Wolne miejsca: **{seats_str}**\n"
            f"🔗 **[👉 KLIKNIJ TUTAJ, ABY KUPIĆ BILET 👈](https://neobus.pl/)**\n"
        )
        blocks.append(block)

    messages, curr = [], header
    for b in blocks:
        if len(curr) + len(b) > 1850:
            messages.append(curr)
            curr = header + b
        else:
            curr += b
    if curr:
        messages.append(curr)

    for msg in messages:
        send_discord_message(msg)
        time.sleep(0.5)


def check_and_notify_new_schedule(active_dates: list):
    """Wysyła powiadomienie, gdy Neobus otworzy rezerwację na kolejny miesiąc."""
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
            f"📅 Nowy zakres sprzedaży wydłużony do: **{furthest}** (było: {prev})\n"
            f"🚀 Bilety promocyjne za 1 zł: https://neobus.pl/"
        )
        send_discord_message(msg)
        with open(LATEST_DATE_FILE, "w", encoding="utf-8") as f:
            f.write(furthest)


# =====================================================================
#                        LOGIKA ZAPYTAŃ API
# =====================================================================


def fetch_neobus_courses(
    from_id: str,
    from_name: str,
    to_id: str,
    to_name: str,
    date_str: str,
    passengers: int = 1,
):
    """Wysyła zapytanie do API Neobusa dla zadanej liczby pasażerów."""
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
            "passengers": str(passengers),
            "date_there": date_str,
            "date_return": "",
            "initial_stop_name": from_name,
            "final_stop_name": to_name,
        }
        resp = session.post(
            "https://neobus.pl/", data=payload, headers=headers, timeout=15
        )
        raw = resp.json() if resp.status_code == 200 else {}
    except Exception:
        return []

    content = raw.get("neotickets", raw) if isinstance(raw, dict) else raw
    data = json.loads(content) if isinstance(content, str) else content

    courses = []
    if (
        isinstance(data, dict)
        and "ga4_data" in data
        and len(data["ga4_data"]) > 0
    ):
        for it in data["ga4_data"][0].get("items", []):
            name = it.get("item_name", "")
            price = it.get("price") or it.get("discount", 0.0)
            try:
                price = float(price)
            except Exception:
                price = 0.0

            match_hours = re.search(
                r"(\d{2}-\d{2})\s*-\s*(\d{2}:\d{2}|\d{2}-\d{2})", name
            )
            hours_str = (
                f"{match_hours.group(1).replace('-', ':')} -> {match_hours.group(2).replace('-', ':')}"
                if match_hours
                else "Standardowy"
            )

            if price > 0:
                courses.append({"hours": hours_str, "price": price})
    return courses


def get_exact_seat_count(
    from_id: str,
    from_name: str,
    to_id: str,
    to_name: str,
    date_str: str,
    target_hours: str,
) -> int:
    """Wyznacza DOKŁADNĄ liczbę wolnych miejsc (1-65) za pomocą wyszukiwania binarnego."""
    low = 1
    high = 65
    exact_seats = 1

    while low <= high:
        mid = (low + high) // 2
        time.sleep(0.25)
        res = fetch_neobus_courses(from_id, from_name, to_id, to_name, date_str, passengers=mid)
        match = [c for c in res if c["hours"] == target_hours]

        if match:
            exact_seats = mid
            low = mid + 1  # Sprawdzamy czy da się zarezerwować jeszcze więcej
        else:
            high = mid - 1 # Za dużo osób, zmniejszamy limit

    return exact_seats


def check_route(
    route_label: str,
    from_id: str,
    from_name: str,
    to_id: str,
    to_name: str,
    dates_list: list,
):
    print(f"🚌 Sprawdzam trasę: {route_label}...")
    courses = []
    empty_days = 0

    for d in dates_list:
        found = fetch_neobus_courses(
            from_id, from_name, to_id, to_name, d, passengers=1
        )
        if found:
            empty_days = 0
            for c in found:
                courses.append({
                    "route": route_label,
                    "date": d,
                    "hours": c["hours"],
                    "price": c["price"],
                    "from_id": from_id,
                    "from_name": from_name,
                    "to_id": to_id,
                    "to_name": to_name,
                    "seats": "B/D",
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
    print("=== MONITORING NEOBUS (CENY + PRECYZYJNA LICZBA MIEJSC) ===")
    dates = generate_dynamic_dates(DAYS_FORWARD_SEARCH)

    # 1. Pobieranie podstawowej siatki kursów
    courses_gli_dom = check_route(
        "Gliwice -> Domaradz",
        STOPS["gliwice"]["id"],
        STOPS["gliwice"]["name"],
        STOPS["domaradz"]["id"],
        STOPS["domaradz"]["name"],
        dates,
    )

    courses_dom_gli = check_route(
        "Domaradz -> Gliwice",
        STOPS["domaradz"]["id"],
        STOPS["domaradz"]["name"],
        STOPS["gliwice"]["id"],
        STOPS["gliwice"]["name"],
        dates,
    )

    # 2. Wykrywanie nowo otwartej puli terminów
    all_active_dates = list(
        {c["date"] for c in (courses_gli_dom + courses_dom_gli)}
    )
    check_and_notify_new_schedule(all_active_dates)

    # 3. Filtrowanie Twoich wybranych terminów i badanie DOKŁADNEJ liczby miejsc
    my_cheap_tickets = []

    for c in courses_gli_dom:
        if 0 < c["price"] <= TARGET_MAX_PRICE and c["date"] in MY_TRIP_DATES_GLIWICE_DOMARADZ:
            print(f"🔍 Badam dokładną liczbę miejsc dla: Gliwice->Domaradz ({c['date']} {c['hours']})...")
            c["seats"] = get_exact_seat_count(
                c["from_id"], c["from_name"], c["to_id"], c["to_name"], c["date"], c["hours"]
            )
            my_cheap_tickets.append(c)

    for c in courses_dom_gli:
        if 0 < c["price"] <= TARGET_MAX_PRICE and c["date"] in MY_TRIP_DATES_DOMARADZ_GLIWICE:
            print(f"🔍 Badam dokładną liczbę miejsc dla: Domaradz->Gliwice ({c['date']} {c['hours']})...")
            c["seats"] = get_exact_seat_count(
                c["from_id"], c["from_name"], c["to_id"], c["to_name"], c["date"], c["hours"]
            )
            my_cheap_tickets.append(c)

    # 4. Zapis do plików CSV (teraz już z wpisaną dokładną liczbą miejsc)
    save_route_to_csv(courses_gli_dom, CSV_GLIWICE_DOMARADZ)
    save_route_to_csv(courses_dom_gli, CSV_DOMARADZ_GLIWICE)

    # 5. Wysłanie powiadomień na Discord
    if my_cheap_tickets:
        print(f"🚨 Znaleziono {len(my_cheap_tickets)} tanich biletów na Twoje terminy!")
        send_discord_alert(my_cheap_tickets)
    else:
        print(f"[i] Brak tanich biletów (<= {TARGET_MAX_PRICE:.2f} PLN) na Twoje zaplanowane wyjazdy.")


if __name__ == "__main__":
    main()
