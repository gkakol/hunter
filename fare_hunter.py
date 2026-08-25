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

TARGET_MAX_PRICE = 97.00  # Próg promocyjny (PLN)
TICKET_TYPE = "normal"  # 'student' lub 'normal'
DAYS_FORWARD_SEARCH = 120  # Sprawdzany zakres w przód

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
        prev_price = last_prices.get(key)

        if prev_price is None or abs(c["price"] - prev_price) > 0.01:
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
        print(f"⚡ [{csv_filename}] Ceny bez zmian.")


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
  """Wysyła estetyczny alert o tanich biletach z bezpośrednimi linkami."""
  if not DISCORD_WEBHOOK_URL or not cheap_tickets:
    return

  count = len(cheap_tickets)
  header = (
      f"🔥 **ZNALEZIONO TANIE BILETY NA TWOJE TERMINY ({count} szt.)!**"
      " @everyone\n"
  )

  blocks = []
  for t in cheap_tickets:
    # Bezpośredni link i podsumowanie konkretnego kursu
    block = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 **{t['route']}** | 📅 **{t['date']}**\n"
        f"⏰ Godzina: **{t['hours']}**\n"
        f"💰 Cena: **{t['price']:.2f} PLN** | 💺 **{t.get('seat_info', 'Dostępne')}**\n"
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


def probe_seat_availability(
    from_id: str,
    from_name: str,
    to_id: str,
    to_name: str,
    date_str: str,
    target_hours: str,
) -> str:
    """Bada ile miejsc w promocyjnej cenie można maksymalnie zarezerwować."""
    # Testujemy progi: 2, 4, 8, 15 osób
    probe_levels = [2, 4, 8, 15]
    max_confirmed = 1

    for p in probe_levels:
        time.sleep(0.3)
        res = fetch_neobus_courses(
            from_id, from_name, to_id, to_name, date_str, passengers=p
        )
        match = [c for c in res if c["hours"] == target_hours]
        if match:
            max_confirmed = p
        else:
            # Jeśli dla 'p' pasażerów kurs nie jest dostępny, kończymy badanie
            break

    if max_confirmed >= 15:
        return "Duża pula (15+ wolnych miejsc)"
    elif max_confirmed >= 8:
        return "Pula 8+ wolnych miejsc"
    elif max_confirmed >= 4:
        return "Pula 4+ wolnych miejsc"
    elif max_confirmed >= 2:
        return "Pula 2-3 wolne miejsca"
    else:
        return "Ostatnie pojedyncze miejsce!"


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
    print("=== MONITORING NEOBUS (CENY + SONDOWANIE DOSTĘPNOŚCI MIEJSC) ===")
    dates = generate_dynamic_dates(DAYS_FORWARD_SEARCH)

    # 1. Trasa: Gliwice -> Domaradz
    courses_gli_dom = check_route(
        "Gliwice -> Domaradz",
        STOPS["gliwice"]["id"],
        STOPS["gliwice"]["name"],
        STOPS["domaradz"]["id"],
        STOPS["domaradz"]["name"],
        dates,
    )
    save_route_to_csv(courses_gli_dom, CSV_GLIWICE_DOMARADZ)

    # 2. Trasa: Domaradz -> Gliwice
    courses_dom_gli = check_route(
        "Domaradz -> Gliwice",
        STOPS["domaradz"]["id"],
        STOPS["domaradz"]["name"],
        STOPS["gliwice"]["id"],
        STOPS["gliwice"]["name"],
        dates,
    )
    save_route_to_csv(courses_dom_gli, CSV_DOMARADZ_GLIWICE)

    # 3. Wykrywanie nowej puli terminów
    all_active_dates = list(
        {c["date"] for c in (courses_gli_dom + courses_dom_gli)}
    )
    check_and_notify_new_schedule(all_active_dates)

    # 4. Filtrowanie okazji TYLKO na Twoje wybrane dni wyjazdu
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

    # 5. Gdy znaleziono tanie bilety — badamy dostępność foteli i wysyłamy alert
    if my_cheap_tickets:
        print(
            f"🚨 Znaleziono {len(my_cheap_tickets)} tanich biletów! Badam dostępność miejsc..."
        )
        for ticket in my_cheap_tickets:
            ticket["seat_info"] = probe_seat_availability(
                ticket["from_id"],
                ticket["from_name"],
                ticket["to_id"],
                ticket["to_name"],
                ticket["date"],
                ticket["hours"],
            )
        send_discord_alert(my_cheap_tickets)
    else:
        print(
            f"[i] Brak tanich biletów (<= {TARGET_MAX_PRICE:.2f} PLN) na Twoje zaplanowane wyjazdy."
        )


if __name__ == "__main__":
    main()
