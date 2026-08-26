import csv
from datetime import date, timedelta
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# =====================================================================
#                        KONFIGURACJA
# =====================================================================

MY_TRIP_DATES_GLIWICE_DOMARADZ = [
    "11.09.2026", "16.09.2026", "17.09.2026", "25.09.2026",
    "02.10.2026", "09.10.2026", "16.10.2026", "23.10.2026",
    "30.10.2026", "06.11.2026", "10.11.2026", "13.11.2026", "20.11.2026"
]

MY_TRIP_DATES_DOMARADZ_GLIWICE = [
    "13.09.2026", "20.09.2026", "27.09.2026", "04.10.2026",
    "11.10.2026", "18.10.2026", "25.10.2026", "02.11.2026",
    "08.11.2026", "15.11.2026", "22.11.2026"
]

TARGET_MAX_PRICE = 60.00
TICKET_TYPE = "normal"
DAYS_FORWARD_SEARCH = 120
MAX_WORKERS = 8

CSV_GLIWICE_DOMARADZ = "ceny_gliwice_domaradz.csv"
CSV_DOMARADZ_GLIWICE = "ceny_domaradz_gliwice.csv"
LATEST_DATE_FILE = "ostatnia_data_sprzedazy.txt"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

STOPS = {
    "gliwice": {"id": "123", "name": "GLIWICE Centrum Przesiadkowe ul. Składowa 8a"},
    "domaradz": {"id": "47", "name": "DOMARADZ "}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://neobus.pl",
    "Referer": "https://neobus.pl/"
}


# =====================================================================
#                   DYNAMIKA DAT I BAZA CSV
# =====================================================================

def generate_dynamic_dates(days_count: int) -> list:
    today = date.today()
    return [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(days_count)]


def load_known_seats(csv_filename: str) -> dict:
    """Wczytuje ostatnio znany stan wolnych miejsc z CSV."""
    known = {}
    if os.path.isfile(csv_filename):
        try:
            with open(csv_filename, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("Data kursu"), row.get("Godzina kursu"))
                    val = row.get("Wolne miejsca", "").strip()
                    if val.isdigit():
                        known[key] = int(val)
        except Exception:
            pass
    return known


def save_route_to_csv(courses_list: list, csv_filename: str):
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
                        seats = row.get("Wolne miejsca") or "B/D"
                        last_records[key] = (price, str(seats).strip())
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"[!] Ostrzeżenie przy odczycie {csv_filename}: {e}")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    records_to_add = []

    for c in courses_list:
        key = (c["date"], c["hours"])
        prev = last_records.get(key)
        curr_seats_str = str(c.get("seats", "B/D")).strip()

        is_new = prev is None
        price_changed = prev and abs(c["price"] - prev[0]) > 0.01
        seats_changed = prev and prev[1] != curr_seats_str

        if is_new or price_changed or seats_changed:
            records_to_add.append([
                timestamp,
                c["date"],
                c["hours"],
                f"{c['price']:.2f}",
                curr_seats_str
            ])

    if records_to_add:
        with open(csv_filename, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Data sprawdzenia", "Data kursu", "Godzina kursu", "Cena (PLN)", "Wolne miejsca"])
            writer.writerows(records_to_add)
        print(f"💾 [{csv_filename}] Zaktualizowano {len(records_to_add)} wierszy.")
    else:
        print(f"⚡ [{csv_filename}] Ceny i stan miejsc bez zmian.")


# =====================================================================
#                   POWIADOMIENIA DISCORD
# =====================================================================

def send_discord_message(content: str):
    if not DISCORD_WEBHOOK_URL:
        return
    headers = {"Content-Type": "application/json"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"username": "Neobus Sentinel", "content": content}, headers=headers, timeout=10)
    except Exception as e:
        print(f"[!] Błąd Discord: {e}")


def send_discord_alert(cheap_tickets: list):
    if not DISCORD_WEBHOOK_URL or not cheap_tickets:
        return

    count = len(cheap_tickets)
    header = f"🔥 **ZNALEZIONO TANIE BILETY NA TWOJE TERMINY ({count} szt.)!** @everyone\n"
    
    blocks = []
    for t in cheap_tickets:
        seats_str = f"{t.get('seats')} szt." if str(t.get('seats')).isdigit() else "Dostępne"
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
        time.sleep(0.3)


def check_and_notify_new_schedule(active_dates: list):
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
#                    ZAPYTANIA API I FAST PROBING
# =====================================================================

def query_neobus(
    session: requests.Session,
    from_id: str,
    from_name: str,
    to_id: str,
    to_name: str,
    date_str: str,
    passengers: int = 1,
    retries: int = 3,
):
  """Wysyła zapytanie z automatycznym wznawianiem przy błędach sieciowych."""
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

  for attempt in range(retries):
    try:
      resp = session.post(
          "https://neobus.pl/", data=payload, headers=HEADERS, timeout=12
      )
      if resp.status_code == 200:
        raw = resp.json()
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
                f"{match_hours.group(1).replace('-', ':')} ->"
                f" {match_hours.group(2).replace('-', ':')}"
                if match_hours
                else "Standardowy"
            )

            if price > 0:
              courses.append({"hours": hours_str, "price": price})
        return (
            courses  # Zwracamy listę znalezionych kursów (może być pusta jeśli brak miejsc)
        )
    except Exception:
      time.sleep(0.3)

  return None  # Zwracamy None TYLKO w przypadku realnego błędu sieci


def get_fast_seat_count(
    from_id: str,
    from_name: str,
    to_id: str,
    to_name: str,
    date_str: str,
    target_hours: str,
    known_seats: int = None,
) -> int:
  """Stabilne badanie z odpornością na zakłócenia połączenia."""
  session = requests.Session()

  # 1. Szybki test zgodności ze starym stanem
  if known_seats and 1 <= known_seats <= 50:
    res = query_neobus(
        session,
        from_id,
        from_name,
        to_id,
        to_name,
        date_str,
        passengers=known_seats,
    )
    if res is not None and any(c["hours"] == target_hours for c in res):
      if known_seats == 50:
        return 50
      res_plus = query_neobus(
          session,
          from_id,
          from_name,
          to_id,
          to_name,
          date_str,
          passengers=known_seats + 1,
      )
      if res_plus is not None and not any(
          c["hours"] == target_hours for c in res_plus
      ):
        return known_seats
      high = 50
    else:
      high = known_seats
  else:
    high = 50

  # 2. Binary Search odporne na timeouty
  low = 1
  exact_seats = 1

  while low <= high:
    mid = (low + high) // 2
    res = query_neobus(
        session, from_id, from_name, to_id, to_name, date_str, passengers=mid
    )

    if res is None:
      # W razie błędu sieci nie ucinamy przedziału, tylko ponawiamy krok
      continue

    if any(c["hours"] == target_hours for c in res):
      exact_seats = mid
      low = mid + 1
    else:
      high = mid - 1

  return exact_seats

def enrich_course_with_seats(course: dict) -> dict:
    course["seats"] = get_fast_seat_count(
        course["from_id"],
        course["from_name"],
        course["to_id"],
        course["to_name"],
        course["date"],
        course["hours"],
        course.get("known_seats")
    )
    return course


def check_route_base(route_label: str, from_id: str, from_name: str, to_id: str, to_name: str, dates_list: list, known_dict: dict):
    print(f"🚌 Skanuję siatkę połączeń: {route_label}...")
    session = requests.Session()
    
    courses = []
    empty_days = 0

    for d in dates_list:
        found = query_neobus(session, from_id, from_name, to_id, to_name, d, passengers=1)
        if found:
            empty_days = 0
            for c in found:
                k_seats = known_dict.get((d, c["hours"]))
                courses.append({
                    "route": route_label,
                    "date": d,
                    "hours": c["hours"],
                    "price": c["price"],
                    "from_id": from_id,
                    "from_name": from_name,
                    "to_id": to_id,
                    "to_name": to_name,
                    "known_seats": k_seats,
                    "seats": "B/D"
                })
        else:
            empty_days += 1

        if empty_days >= 6:
            print(f"🛑 [Koniec puli] Brak biletów od {d}. Koniec trasy.")
            break

    return courses


# =====================================================================
#                           GŁÓWNY PROGRAM
# =====================================================================

def main():
    start_t = time.time()
    print("=== SZYBKI MONITORING NEOBUS (DELTA CHECK 100% MIEJSC) ===")

    dates = generate_dynamic_dates(DAYS_FORWARD_SEARCH)

    known_gli_dom = load_known_seats(CSV_GLIWICE_DOMARADZ)
    known_dom_gli = load_known_seats(CSV_DOMARADZ_GLIWICE)

    # 1. Pobieranie siatki połączeń
    courses_gli_dom = check_route_base("Gliwice -> Domaradz", STOPS["gliwice"]["id"], STOPS["gliwice"]["name"], STOPS["domaradz"]["id"], STOPS["domaradz"]["name"], dates, known_gli_dom)
    courses_dom_gli = check_route_base("Domaradz -> Gliwice", STOPS["domaradz"]["id"], STOPS["domaradz"]["name"], STOPS["gliwice"]["id"], STOPS["gliwice"]["name"], dates, known_dom_gli)

    # 2. Powiadomienie o nowej puli
    all_active_dates = list({c["date"] for c in (courses_gli_dom + courses_dom_gli)})
    check_and_notify_new_schedule(all_active_dates)

    all_courses = courses_gli_dom + courses_dom_gli
    total_count = len(all_courses)
    print(f"🚀 Szybkie badanie miejsc metodą Delta Check dla {total_count} kursów ({MAX_WORKERS} wątków)...")

    # 3. Równoległe badanie miejsc
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(enrich_course_with_seats, course) for course in all_courses]
        done = 0
        for _ in as_completed(futures):
            done += 1
            if done % 50 == 0 or done == total_count:
                print(f"   ⏳ Zweryfikowano {done}/{total_count} kursów...")

    # 4. Zapis do plików CSV
    save_route_to_csv(courses_gli_dom, CSV_GLIWICE_DOMARADZ)
    save_route_to_csv(courses_dom_gli, CSV_DOMARADZ_GLIWICE)

    # 5. Filtrowanie okazji i wysyłanie alertów Discord
    my_cheap_tickets = []
    for c in courses_gli_dom:
        if 0 < c["price"] <= TARGET_MAX_PRICE and c["date"] in MY_TRIP_DATES_GLIWICE_DOMARADZ:
            my_cheap_tickets.append(c)

    for c in courses_dom_gli:
        if 0 < c["price"] <= TARGET_MAX_PRICE and c["date"] in MY_TRIP_DATES_DOMARADZ_GLIWICE:
            my_cheap_tickets.append(c)

    if my_cheap_tickets:
        print(f"🚨 Znaleziono {len(my_cheap_tickets)} tanich biletów!")
        send_discord_alert(my_cheap_tickets)
    else:
        print(f"[i] Brak tanich biletów (<= {TARGET_MAX_PRICE:.2f} PLN) na Twoje terminy.")

    total_time = time.time() - start_t
    print(f"⏱️ Zbadano 100% kursów w czasie: {total_time:.2f} s")


if __name__ == "__main__":
    main()
