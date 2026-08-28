import os
import subprocess
import time

# Ustaw swój webhook do Discorda
os.environ["DISCORD_WEBHOOK_URL"] = "TUTAJ_WKLEJ_SWOJ_WEBHOOK_DISCORD"

INTERVAL_MINUTES = 30

while True:
  print("\n" + "=" * 50)
  print(
      f"🚀 Rozpoczynam sprawdzanie: {time.strftime('%Y-%m-%d %H:%M:%S')}"
  )

  # 1. Pobieranie danych i powiadomienia
  subprocess.run(["python", "fare_hunter.py"])

  # 2. Generowanie wykresów
  subprocess.run(["python", "generate_chart.py"])

  # 3. Wypychanie zmian na GitHub (opcjonalnie)
  try:
    subprocess.run(["git", "add", "-A"])
    subprocess.run(
        ["git", "commit", "-m", "Aktualizacja lokalna [auto]"],
        capture_output=True,
    )
    subprocess.run(["git", "pull", "--rebase", "origin", "main"])
    subprocess.run(["git", "push"])
  except Exception as e:
    print(f"[!] Błąd synchronizacji Git: {e}")

  print(
      f"⏳ Czekam {INTERVAL_MINUTES} minut do kolejnego sprawdzenia..."
  )
  time.sleep(INTERVAL_MINUTES * 60)
