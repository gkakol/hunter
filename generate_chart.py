import os
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

CSV_FILE = "ceny_historia.csv"
OUTPUT_IMAGE = "wykres_cen.png"


def generate_chart():
    if not os.path.isfile(CSV_FILE):
        print("[!] Brak pliku CSV do wygenerowania wykresu.")
        return

    # Wczytanie danych
    df = pd.read_csv(CSV_FILE)
    if df.empty:
        print("[!] Plik CSV jest pusty.")
        return

    # Konwersja kolumny z datą sprawdzenia na format DateTime
    df["Data sprawdzenia"] = pd.to_datetime(df["Data sprawdzenia"])
    df["Cena (PLN)"] = pd.to_numeric(df["Cena (PLN)"], errors="coerce")

    # Tworzenie etykiety kursu (np. "11.09 | 00:20 -> 05:24")
    df["Kurs"] = df["Data kursu"] + " (" + df["Godzina kursu"] + ")"

    # Ustawienie stylu wykresu
    plt.style.use("seaborn-v0_8-darkgrid" if "seaborn-v0_8-darkgrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    trasy = [
        ("Gliwice -> Domaradz", axes[0], "#1f77b4"),
        ("Domaradz -> Gliwice", axes[1], "#ff7f0e"),
    ]

    for trasa_nazwa, ax, color in trasy:
        subset = df[df["Trasa"] == trasa_nazwa]
        if subset.empty:
            ax.set_title(f"Trasa: {trasa_nazwa} (Brak danych)", fontsize=13, fontweight="bold")
            continue

        # Rysowanie linii dla każdego unikalnego kursu
        unikalne_kursy = subset["Kurs"].unique()
        for kurs in unikalne_kursy:
            kurs_data = subset[subset["Kurs"] == kurs].sort_values("Data sprawdzenia")
            ax.plot(
                kurs_data["Data sprawdzenia"],
                kurs_data["Cena (PLN)"],
                marker="o",
                markersize=4,
                label=kurs,
                alpha=0.8,
            )

        ax.set_title(f"📊 Historia i trend cen: {trasa_nazwa}", fontsize=13, fontweight="bold")
        ax.set_ylabel("Cena (PLN)", fontsize=11)
        ax.axhline(y=45.00, color="red", linestyle="--", linewidth=1.2, label="Próg promocji (45 PLN)")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0, fontsize=8)

    # Formatowanie osi X (czas)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    axes[1].set_xlabel("Data i godzina pomiaru", fontsize=11)
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ [Wykres] Wygenerowano pomyślnie i zapisano do {OUTPUT_IMAGE}")


if __name__ == "__main__":
    generate_chart()
