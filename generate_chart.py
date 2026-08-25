import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def create_route_chart(csv_file: str, output_img: str, route_title: str, main_color: str):
    if not os.path.isfile(csv_file) or os.path.getsize(csv_file) == 0:
        return

    try:
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip()
    except Exception:
        return

    df["Data sprawdzenia"] = pd.to_datetime(df["Data sprawdzenia"], errors="coerce")
    df["Cena (PLN)"] = pd.to_numeric(df["Cena (PLN)"], errors="coerce")
    df = df[df["Cena (PLN)"] > 0].dropna(subset=["Data sprawdzenia", "Cena (PLN)"])
    df["Data kursu_dt"] = pd.to_datetime(df["Data kursu"], format="%d.%m.%Y", errors="coerce")
    df = df.dropna(subset=["Data kursu_dt"])

    if df.empty:
        return

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, (ax_trend, ax_cal) = plt.subplots(2, 1, figsize=(14, 8))

    # --- 1. GÓRNY WYKRES: HISTORIA MINIMALNEJ CENY ---
    min_history = df.groupby("Data sprawdzenia")["Cena (PLN)"].min().reset_index()
    ax_trend.plot(
        min_history["Data sprawdzenia"],
        min_history["Cena (PLN)"],
        color=main_color,
        linewidth=2.2,
        marker="o",
        markersize=4,
        label=f"{route_title} (Min. cena)",
    )
    ax_trend.axhline(y=45.00, color="#d32f2f", linestyle="--", linewidth=1.2, label="Próg promocyjny (45 PLN)")
    ax_trend.set_title(f"📈 {route_title} — Historia minimalnej ceny w czasie", fontsize=11, fontweight="bold")
    ax_trend.set_ylabel("Cena (PLN)", fontsize=9)
    ax_trend.legend(loc="upper right", frameon=True, fontsize=8)
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))

    # --- 2. DOLNY WYKRES: PEŁNY KALENDARZ DNI (OSTATNIA ZNANA CENA KAŻDEGO DNIA) ---
    # Bierzemy ostatni znany rekord dla każdego dnia i kursu
    latest_per_course = df.sort_values("Data sprawdzenia").groupby(["Data kursu_dt", "Godzina kursu"]).last().reset_index()
    daily_min_prices = latest_per_course.groupby("Data kursu_dt")["Cena (PLN)"].min().reset_index()

    ax_cal.plot(
        daily_min_prices["Data kursu_dt"],
        daily_min_prices["Cena (PLN)"],
        color=main_color,
        linewidth=2,
        marker="s",
        markersize=3.5,
        label="Aktualna najniższa cena w danym dniu",
    )
    ax_cal.axhline(y=45.00, color="#d32f2f", linestyle="--", linewidth=1.2)
    ax_cal.set_title(f"📅 {route_title} — Kalendarz cen na kolejne dni wyjazdu", fontsize=11, fontweight="bold")
    ax_cal.set_ylabel("Cena (PLN)", fontsize=9)
    ax_cal.set_xlabel("Data podróży", fontsize=9)
    ax_cal.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax_cal.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax_cal.legend(loc="upper right", frameon=True, fontsize=8)

    plt.tight_layout()
    plt.savefig(output_img, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Wygenerowano wykres: {output_img}")


def generate_all_charts():
    create_route_chart(
        csv_file="ceny_gliwice_domaradz.csv",
        output_img="wykres_gliwice_domaradz.png",
        route_title="Gliwice -> Domaradz",
        main_color="#007acc",
    )
    create_route_chart(
        csv_file="ceny_domaradz_gliwice.csv",
        output_img="wykres_domaradz_gliwice.png",
        route_title="Domaradz -> Gliwice",
        main_color="#e65100",
    )


if __name__ == "__main__":
    generate_all_charts()
