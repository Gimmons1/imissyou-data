import requests
import feedparser
import json
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
# Fonti affidabili richieste
FEEDS = [
    "https://www.ansa.it/sito/notizie/cultura/cultura_rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.reutersagency.com/feed/" # Esempio Reuters
]

KEYWORDS = ["morto", "morta", "deceduto", "deceduta", "scomparsa", "scomparso", "addio a", "died", "passed away", "death of"]
JSON_FILE = "library.json"

def get_wikipedia_info(name, lang="it"):
    """Interroga Wikipedia per ottenere slug e bio sintetica"""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "slug": data.get("titles", {}).get("canonical", ""),
                "bio": data.get("extract", ""),
                "img": data.get("originalimage", {}).get("source", None)
            }
    except:
        return None
    return None

def run_updater():
    # 1. Carica database esistente
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            library = json.load(f)
    else:
        library = []

    existing_names = [p["name"].lower() for p in library]
    new_entries = []

    # 2. Scansiona i Feed
    print("Scansione feed in corso...")
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title.lower()
            
            # 3. Cerca parole chiave
            if any(key in title for key in KEYWORDS):
                # Estrazione rozza del nome (migliorabile con IA in futuro)
                # Qui facciamo una ricerca su Wikipedia basandoci sul titolo
                potential_name = entry.title.replace("Addio a ", "").replace("Morto ", "").split(",")[0].strip()
                
                if potential_name.lower() not in existing_names:
                    print(f"Possibile decesso rilevato: {potential_name}")
                    
                    # Recupera dettagli da Wiki
                    info = get_wikipedia_info(potential_name)
                    if info and info["slug"]:
                        new_person = {
                            "name": potential_name,
                            "slugs": {"IT": info["slug"], "EN": info["slug"]},
                            "bio": info["bio"] or "Dettagli in fase di aggiornamento.",
                            "birthDate": "1900-01-01", # Da correggere manualmente o con IA
                            "deathDate": datetime.now().strftime("%Y-%m-%d"),
                            "imageUrl": info["img"]
                        }
                        new_entries.append(new_person)
                        existing_names.append(potential_name.lower())

    # 4. Salva se ci sono novità
    if new_entries:
        library.extend(new_entries)
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"Aggiunte {len(new_entries)} nuove persone.")
    else:
        print("Nessun nuovo decesso rilevato.")

if __name__ == "__main__":
    run_updater()
