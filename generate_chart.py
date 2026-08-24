import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CSV_FILE = "ceny_historia.csv"
OUTPUT_IMAGE = "wykres_cen.png"


def generate_chart():
    if not os.path.isfile(CSV_FILE):
        print("[!] Brak pliku CSV.")
        return

    df = pd.read_csv(CSV_FILE)
    if df.empty:
        return

    # 1. Czyszczenie danych i filtrowanie zer
    df["Data sprawdzenia"] = pd.to_datetime(df["Data sprawdzenia"])
    df["Cena (PLN)"] = pd.to_numeric(df["Cena (PLN)"], errors="coerce")
    df = df[df["Cena (PLN)"] > 0]  # Odrzucamy puste/zerowe kursy

    if df.empty:
        return

    # Parsowanie daty kursu do właściwego formatu DateTime
    df["Data kursu_dt"] = pd.to_datetime(df["Data kursu"], format="%d.%m.%Y")

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, (ax_trend, ax_cal) = plt.subplots(2, 1, figsize=(14, 10))

    # =========================================================================
    # 1. GÓRNY WYKRES: JAK KSZTAŁTOWAŁY SIĘ CENY W CZASIE (HISTORIA MONITORINGU)
    # =========================================================================
    colors = {"Gliwice -> Domaradz": "#007acc", "Domaradz -> Gliwice": "#e65100"}

    for trasa, color in colors.items():
        subset = df[df["Trasa"] == trasa]
        if not subset.empty:
            # Minimalna cena w danym momencie pomiaru
            min_trend = subset.groupby("Data sprawdzenia")["Cena (PLN)"].min().reset_index()
            ax_trend.plot(
                min_trend["Data sprawdzenia"],
                min_trend["Cena (PLN)"],
                label=f"{trasa} (Najniższa dostępna)",
                color=color,
                linewidth=2.2,
                marker="o",
                markersize=4,
            )

    ax_trend.axhline(y=45.00, color="#d32f2f", linestyle="--", linewidth=1.5, label="Próg promocji (45 PLN)")
    ax_trend.set_title("📈 Trend najniższych cen wykrytych w kolejnych pomiarach", fontsize=12, fontweight="bold")
    ax_trend.set_ylabel("Cena (PLN)", fontsize=10)
    ax_trend.legend(loc="upper right", frameon=True, fontsize=9)
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    ax_trend.grid(True, linestyle=":", alpha=0.6)

    # =========================================================================
    # 2. DOLNY WYKRES: KALENDARZ CEN NA KOLEJNE DNI (NAJŚWIEŻSZY STAN)
    # =========================================================================
    ostatnie_sprawdzenie = df["Data sprawdzenia"].max()
    latest_df = df[df["Data sprawdzenia"] == ostatnie_sprawdzenie].copy()

    for trasa, color in colors.items():
        subset = latest_df[latest_df["Trasa"] == trasa]
        if not subset.empty:
            # Najniższa cena w danym dniu wyjazdu
            daily_min = subset.groupby("Data kursu_dt")["Cena (PLN)"].min().reset_index()
            daily_min = daily_min.sort_values("Data kursu_dt")

            ax_cal.plot(
                daily_min["Data kursu_dt"],
                daily_min["Cena (PLN)"],
                label=trasa,
                color=color,
                linewidth=2,
                marker="s",
                markersize=3.5,
                alpha=0.9,
            )

    ax_cal.axhline(y=45.00, color="#d32f2f", linestyle="--", linewidth=1.5, label="Próg promocji (45 PLN)")
    ax_cal.set_title(
        f"📅 Kalendarz cen według daty podróży (Stan na: {ostatnie_sprawdzenie.strftime('%d.%m.%Y %H:%M')})",
        fontsize=12,
        fontweight="bold",
    )
    ax_cal.set_ylabel("Cena minimalna (PLN)", fontsize=10)
    ax_cal.set_xlabel("Data podróży", fontsize=10)

    # Czytelne formatowanie osi dat podróży (co 5 dni)
    ax_cal.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax_cal.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax_cal.tick_params(axis="x", rotation=0)
    ax_cal.legend(loc="upper right", frameon=True, fontsize=9)
    ax_cal.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"✅ [Wykres] Wygenerowano czytelny wykres do {OUTPUT_IMAGE}")


if __name__ == "__main__":
    generate_chart()
