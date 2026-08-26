import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

CSV_GLIWICE_DOMARADZ = "ceny_gliwice_domaradz.csv"
CSV_DOMARADZ_GLIWICE = "ceny_domaradz_gliwice.csv"

IMG_GLIWICE_DOMARADZ = "heatmapa_gliwice_domaradz.png"
IMG_DOMARADZ_GLIWICE = "heatmapa_domaradz_gliwice.png"


def create_route_calendar_heatmap(csv_file: str, output_img: str, route_title: str):
    if not os.path.isfile(csv_file):
        return

    df = pd.read_csv(csv_file)
    df["Wolne miejsca"] = pd.to_numeric(df["Wolne miejsca"], errors="coerce")
    df["dt"] = pd.to_datetime(df["Data kursu"], format="%d.%m.%Y", errors="coerce")
    df = df.dropna(subset=["dt", "Wolne miejsca"])

    # Najnowszy stan dla każdego kursu
    df_latest = df.sort_values("Data sprawdzenia").groupby(
        ["Data kursu", "Godzina kursu"], as_index=False
    ).last()

    dni_pl = {
        "Monday": "Pn", "Tuesday": "Wt", "Wednesday": "Śr",
        "Thursday": "Cz", "Friday": "Pt", "Saturday": "Sb", "Sunday": "Nd"
    }
    df_latest["Dzien_skrot"] = df_latest["dt"].dt.day_name().map(dni_pl)
    df_latest["Data_Etykieta"] = df_latest["dt"].dt.strftime("%d.%m") + " (" + df_latest["Dzien_skrot"] + ")"
    
    df_latest["Godzina_odjazdu"] = df_latest["Godzina kursu"].apply(
        lambda x: x.split(" -> ")[0] if " -> " in str(x) else str(x)
    )

    # Sortowanie chronologiczne
    df_latest = df_latest.sort_values("dt", ascending=True)

    pivot = df_latest.pivot_table(
        index="Data_Etykieta",
        columns="Godzina_odjazdu",
        values="Wolne miejsca",
        aggfunc="last"
    )

    # Zachowanie kolejności dat chronologicznie
    unikalne_daty = df_latest["Data_Etykieta"].unique()
    pivot = pivot.reindex(unikalne_daty)

    # Dynamiczna wysokość wykresu w zależności od liczby dni
    fig_height = max(10, len(pivot) * 0.28)
    plt.figure(figsize=(8, fig_height))

    # Paleta YlOrRd_r (Odwrócona: mało miejsc = ciemna czerwień, 50 miejsc = jasny żółty)
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0f",
        cmap="YlOrRd_r",
        vmin=0,
        vmax=50,
        cbar_kws={"label": "Liczba wolnych miejsc (im czerwniej, tym mniej)"},
        linewidths=0.5,
        linecolor="#dddddd"
    )

    plt.title(f"Wolne miejsca na kursach: {route_title}\n(Ciemnoczerwony = końcówka miejsc)", fontsize=13, pad=15)
    plt.xlabel("Godzina odjazdu", fontsize=11, labelpad=10)
    plt.ylabel("Data kursu", fontsize=11, labelpad=10)
    plt.tight_layout()
    plt.savefig(output_img, dpi=140)
    plt.close()
    print(f"✅ Wygenerowano czytelną heatmapę: {output_img}")


def main():
    create_route_calendar_heatmap(
        CSV_GLIWICE_DOMARADZ,
        IMG_GLIWICE_DOMARADZ,
        "Gliwice ➔ Domaradz"
    )
    create_route_calendar_heatmap(
        CSV_DOMARADZ_GLIWICE,
        IMG_DOMARADZ_GLIWICE,
        "Domaradz ➔ Gliwice"
    )


if __name__ == "__main__":
    main()
