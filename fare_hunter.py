import csv
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

TARGET_MAX_PRICE = 50.00
TICKET_TYPE = "normal"  # 'student' lub 'normal'
CSV_FILE = "ceny_historia.csv"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

STOPS = {
    "gliwice": {
        "id": "123",
        "name": "GLIWICE Centrum Przesiadkowe ul. Składowa 8a",
    },
    "domaradz": {"id": "47", "name": "DOMARADZ "},
}


def save_to_csv(courses_list: list):
    """Zapisuje kurs do CSV tylko wtedy, gdy zmieniła się cena lub kurs jest nowy."""
    if not courses_list:
        return

    file_exists = os.path.isfile(CSV_FILE)
    last_known_prices = {}

    # 1. Odczytujemy ostatnio zarejestrowaną cenę dla każdego kursu
    if file_exists:
        try:
            with open(CSV_FILE, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Klucz jednoznacznie identyfikujący kurs: (Trasa, Data, Godziny)
                    key = (
                        row.get("Trasa"),
                        row.get("Data kursu"),
                        row.get("Godzina kursu"),
                    )
                    try:
                        last_known_prices[key] = float(row.get("Cena (PLN)", 0))
                    except ValueError:
                        pass
        except Exception as e:
            print(f"[!] Ostrzeżenie przy czytaniu CSV: {e}")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    records_to_add = []

    # 2. Porównujemy świeżo pobrane ceny z poprzednimi
    for c in courses_list:
        key = (c["route"], c["date"], c["hours"])
        prev_price = last_known_prices.get(key)

        # Zapisujemy tylko jeśli:
        # a) Nigdy wcześniej nie widzieliśmy tego kursu (prev_price is None)
        # b) Cena uległa zmianie (abs(c["price"] - prev_price) > 0.01)
        if prev_price is None or abs(c["price"] - prev_price) > 0.01:
            records_to_add.append([
                timestamp,
                c["route"],
                c["date"],
                c["hours"],
                f"{c['price']:.2f}",
            ])

    # 3. Dopisujemy do pliku tylko realne zmiany
    if records_to_add:
        with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Data sprawdzenia",
                    "Trasa",
                    "Data kursu",
                    "Godzina kursu",
                    "Cena (PLN)",
                ])
            writer.writerows(records_to_add)
        print(
            f"💾 [Optymalizacja CSV] Wykryto i zapisano {len(records_to_add)} nowych/zmienionych cen (odrzucono {len(courses_list) - len(records_to_add)} duplikatów)."
        )
    else:
        print(
            f"⚡ [Optymalizacja CSV] Ceny bez zmian. Pomijam dopisywanie {len(courses_list)} duplikatów."
        )


def send_discord_alert(cheap_tickets: list):
    if not DISCORD_WEBHOOK_URL:
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

    ticket_blocks = [
        f"📍 **{t.get('route')}** ({t.get('date')})\n"
        f"   ⏰ Kurs: **{t.get('hours')}** | 💰 Cena: **{t.get('price'):.2f} PLN**\n"
        for t in cheap_tickets
    ]

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
            requests.post(
                DISCORD_WEBHOOK_URL,
                json={"username": "Neobus Tracker", "content": msg},
                headers=headers,
                timeout=10,
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"[!] Błąd Discord: {e}")


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
    all_courses = []

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
            all_courses.append({
                "route": route_label,
                "date": d,
                "hours": c["hours"],
                "price": c["price"],
            })
        time.sleep(1.5)

    return all_courses


def main():
    print("=== SPRAWDZANIE KURSÓW NEOBUS + ZAPIS DO CSV ===")
    all_courses = []

    if DATES_GLIWICE_DOMARADZ:
        all_courses.extend(
            check_route(
                "Gliwice -> Domaradz",
                STOPS["gliwice"]["id"],
                STOPS["domaradz"]["id"],
                DATES_GLIWICE_DOMARADZ,
            )
        )

    if DATES_DOMARADZ_GLIWICE:
        all_courses.extend(
            check_route(
                "Domaradz -> Gliwice",
                STOPS["domaradz"]["id"],
                STOPS["gliwice"]["id"],
                DATES_DOMARADZ_GLIWICE,
            )
        )

    # 1. Zapisujemy wszystkie kursy do pliku CSV
    if all_courses:
        save_to_csv(all_courses)

    # 2. Wysyłamy alert jeśli są promocyjne bilety
    cheap = [c for c in all_courses if 0 < c["price"] <= TARGET_MAX_PRICE]
    if cheap:
        print(f"\n🚨 Znaleziono {len(cheap)} tanich biletów! Wysyłam alert...")
        send_discord_alert(cheap)
    else:
        print(f"\n[i] Brak biletów w cenie <= {TARGET_MAX_PRICE:.2f} PLN.")


if __name__ == "__main__":
    main()
