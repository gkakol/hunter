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

    # Przygotowanie danych
    df["Data sprawdzenia"] = pd.to_datetime(df["Data sprawdzenia"])
    df["Cena (PLN)"] = pd.to_numeric(df["Cena (PLN)"], errors="coerce")

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, (ax_trend, ax_bar) = plt.subplots(2, 1, figsize=(13, 10))

    # =========================================================================
    # 1. GÓRNY WYKRES: TREND NAJNIŻSZEJ CENY W CZASIE (BEZ SPAMU LEGENDĄ)
    # =========================================================================
    for trasa, color in [("Gliwice -> Domaradz", "#007acc"), ("Domaradz -> Gliwice", "#e65100")]:
        subset = df[df["Trasa"] == trasa]
        if not subset.empty:
            # Grupujemy po dacie sprawdzenia i bierzemy minimalną cenę
            min_prices = subset.groupby("Data sprawdzenia")["Cena (PLN)"].min().reset_index()
            ax_trend.plot(
                min_prices["Data sprawdzenia"],
                min_prices["Cena (PLN)"],
                label=f"{trasa} (Min. cena)",
                color=color,
                linewidth=2.5,
                marker="o",
                markersize=5,
            )

    ax_trend.axhline(y=45.00, color="#d32f2f", linestyle="--", linewidth=1.5, label="Próg promocji (45 PLN)")
    ax_trend.set_title("📈 Trend minimalnych cen na trasach w czasie", fontsize=13, fontweight="bold")
    ax_trend.set_ylabel("Najniższa cena (PLN)", fontsize=11)
    ax_trend.legend(loc="upper right", frameon=True, fontsize=10)
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    ax_trend.grid(True, linestyle=":", alpha=0.6)

    # =========================================================================
    # 2. DOLNY WYKRES: KALENDARZ CEN NAJBLIŻSZYCH DNI (NAJNOWSZY POMIAR)
    # =========================================================================
    # Bierzemy wyłącznie najświeższe sprawdzenie każdego kursu
    ostatnie_sprawdzenie = df["Data sprawdzenia"].max()
    latest_df = df[df["Data sprawdzenia"] == ostatnie_sprawdzenie].copy()

    # Grupowanie cen minimalnych dla poszczególnych dat
    calendar_df = latest_df.groupby(["Data kursu", "Trasa"])["Cena (PLN)"].min().unstack()

    # Kolorowanie słupków: zielony jeśli <= 45 zł, pomarańczowy jeśli standard
    colors = ["#007acc", "#e65100"]
    calendar_df.plot(kind="bar", ax=ax_bar, color=colors, width=0.7, edgecolor="black", linewidth=0.5)

    ax_bar.axhline(y=45.00, color="#d32f2f", linestyle="--", linewidth=1.5)
    ax_bar.set_title(f"📅 Aktualne ceny minimalne według dni podróży (Stan na: {ostatnie_sprawdzenie.strftime('%d.%m.%Y %H:%M')})", fontsize=13, fontweight="bold")
    ax_bar.set_ylabel("Cena minimalna (PLN)", fontsize=11)
    ax_bar.set_xlabel("Data wyjazdu", fontsize=11)
    ax_bar.tick_params(axis="x", rotation=45)
    ax_bar.legend(title="Trasa", loc="upper right", frameon=True)
    ax_bar.grid(True, linestyle=":", alpha=0.6)

    # Dodanie etykiet z ceną nad słupkami
    for p in ax_bar.patches:
        height = p.get_height()
        if not np.isnan(height) and height > 0:
            ax_bar.annotate(
                f"{int(height)} zł",
                (p.get_x() + p.get_width() / 2.0, height),
                ha="center",
                va="bottom",
                fontsize=8,
                xytext=(0, 2),
                textcoords="offset points",
            )

    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"✅ [Wykres] Wygenerowano czytelny dashboard do {OUTPUT_IMAGE}")


if __name__ == "__main__":
    generate_chart()
