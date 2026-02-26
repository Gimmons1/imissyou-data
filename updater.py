import requests
import feedparser
import json
import os
from datetime import datetime

# --- CONFIGURAZIONE CENTRALE OPERATIVA GLOBALE ---
FEEDS = [
    "https://www.ansa.it/sito/notizie/cultura/cultura_rss.xml",
    "https://www.corriere.it/rss/cultura.xml",
    "https://www.repubblica.it/rss/spettacoli_e_cultura/rss2.0.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.reutersagency.com/feed/",
    "http://rss.cnn.com/rss/edition_world.rss",
    "https://www.theguardian.com/world/rss",
    "https://www.lemonde.fr/rss/une.xml",
    "https://www.lefigaro.fr/rss/figaro/culture.xml",
    "https://elpais.com/rss/elpais/in_english.xml",
    "https://elpais.com/rss/cultura/portada.xml"
]

KEYWORDS = [
    "morto", "morta", "deceduto", "deceduta", "addio a", "scomparsa", "scomparso",
    "died", "passed away", "death of", "obituary", "dies at", "rest in peace",
    "est décédé", "est décédée", "mort de", "disparition de",
    "muere", "ha muerto", "fallece", "fallecimiento", "defunción"
]

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_GlobalSentinel/4.0 (https://github.com/Gimmons1)'}

def get_wikipedia_details(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=8) # Timeout stretto!
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

def fetch_feed_safe(url):
    """Scarica il feed in modo sicuro con un timeout. Evita i caricamenti infiniti su GitHub Actions."""
    try:
        # Se un giornale è down, aspettiamo massimo 10 secondi poi passiamo al prossimo
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return feedparser.parse(response.content)
    except Exception as e:
        print(f" [!] Impossibile raggiungere la fonte ({url.split('/')[2]}) - Salto.")
    return None

def run_updater():
    print(f"--- Sentinel Globale Attiva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    existing_names = [p["name"].lower().strip() for p in library]
    new_entries = []

    for feed_url in FEEDS:
        print(f"Monitoraggio: {feed_url.split('/')[2]}")
        feed = fetch_feed_safe(feed_url)
        
        if not feed:
            continue # Salta al prossimo giornale se questo non risponde
            
        for entry in feed.entries:
            title = entry.title.lower()
            if any(key in title for key in KEYWORDS):
                potential_name = entry.title.split(":")[0].split("-")[0].split("(")[0]
                potential_name = potential_name.replace("Addio a ", "").replace("Morto ", "").replace("Morta ", "").replace("Died ", "").strip()
                
                if potential_name.lower() not in existing_names and len(potential_name) > 3:
                    lang = "en"
                    if "ansa" in feed_url or "corriere" in feed_url or "repubblica" in feed_url: lang = "it"
                    elif "lemonde" in feed_url or "lefigaro" in feed_url: lang = "fr"
                    elif "elpais" in feed_url: lang = "es"
                    
                    info = get_wikipedia_details(potential_name, lang)
                    if info and info["slug"]:
                        source_name = feed_url.split("/")[2].replace("www.", "")
                        new_person = {
                            "name": potential_name,
                            "slugs": {"IT": info["slug"], "EN": info["slug"]},
                            "bio": info["bio"] + f" [Rilevato da {source_name}]",
                            "birthDate": "1900-01-01",
                            "deathDate": datetime.now().strftime("%Y-%m-%d"),
                            "imageUrl": info["img"],
                            "approved": False # Le nuove notizie vanno nel Pannello Admin dell'App
                        }
                        new_entries.append(new_person)
                        existing_names.append(potential_name.lower())
                        print(f" > Rilevato: {potential_name} ({lang}) - Inviato in revisione")

    if new_entries:
        library.extend(new_entries)
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"--- Completato: Trovate {len(new_entries)} novità da approvare nell'App ---")
    else:
        print("--- Scansione completata: Nessun nuovo decesso nelle ultime ore ---")

if __name__ == "__main__":
    run_updater()
