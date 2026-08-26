import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

CSV_GLIWICE_DOMARADZ = "ceny_gliwice_domaradz.csv"
CSV_DOMARADZ_GLIWICE = "ceny_domaradz_gliwice.csv"
OUTPUT_HEATMAP = "wykres_oblozenie_heatmap.png"


def generate_occupancy_heatmap():
  dfs = []
  if os.path.isfile(CSV_GLIWICE_DOMARADZ):
    d1 = pd.read_csv(CSV_GLIWICE_DOMARADZ)
    d1["Trasa"] = "Gliwice -> Domaradz"
    dfs.append(d1)
  if os.path.isfile(CSV_DOMARADZ_GLIWICE):
    d2 = pd.read_csv(CSV_DOMARADZ_GLIWICE)
    d2["Trasa"] = "Domaradz -> Gliwice"
    dfs.append(d2)

  if not dfs:
    return

  df = pd.concat(dfs, ignore_index=True)
  df["Wolne miejsca"] = pd.to_numeric(df["Wolne miejsca"], errors="coerce")
  df["dt"] = pd.to_datetime(
      df["Data kursu"], format="%d.%m.%Y", errors="coerce"
  )
  df = df.dropna(subset=["dt", "Wolne miejsca"])

  # Średnie zapełnienie autokaru w %
  df["Zajetosc_%"] = ((50 - df["Wolne miejsca"]) / 50) * 100
  df["Dzien_tyg"] = df["dt"].dt.day_name()
  df["Godzina_odjazdu"] = df["Godzina kursu"].apply(
      lambda x: x.split(" -> ")[0] if " -> " in str(x) else str(x)
  )

  dni_pl = {
      "Monday": "Poniedziałek",
      "Tuesday": "Wtorek",
      "Wednesday": "Środa",
      "Thursday": "Czwartek",
      "Friday": "Piątek",
      "Saturday": "Sobota",
      "Sunday": "Niedziela",
  }
  df["Dzien_tyg"] = df["Dzien_tyg"].map(dni_pl)
  kolejnosc_dni = [
      "Poniedziałek",
      "Wtorek",
      "Środa",
      "Czwartek",
      "Piątek",
      "Sobota",
      "Niedziela",
  ]

  # Bierzemy najnowszy wpis dla każdego konkretnego kursu
  df_latest = df.sort_values("Data sprawdzenia").groupby(
      ["Trasa", "Data kursu", "Godzina kursu"], as_index=False
  ).last()

  pivot = df_latest.pivot_table(
      index="Dzien_tyg",
      columns="Godzina_odjazdu",
      values="Zajetosc_%",
      aggfunc="mean",
  )
  pivot = pivot.reindex(
      [d for d in kolejnosc_dni if d in pivot.index]
  ).fillna(0)

  plt.figure(figsize=(10, 5))
  sns.heatmap(
      pivot,
      annot=True,
      fmt=".0f",
      cmap="YlOrRd",
      cbar_kws={"label": "Średnie zapełnienie (%)"},
      linewidths=0.8,
  )
  plt.title(
      "Średnie obłożenie autokarów Neobus wg dni i godzin (Wszystkie kursy)",
      fontsize=12,
  )
  plt.xlabel("Godzina odjazdu")
  plt.ylabel("Dzień tygodnia")
  plt.tight_layout()
  plt.savefig(OUTPUT_HEATMAP, dpi=150)
  plt.close()
  print(f"✅ Wygenerowano heatmapę: {OUTPUT_HEATMAP}")


if __name__ == "__main__":
  generate_occupancy_heatmap()
