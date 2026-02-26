import requests
import feedparser
import json
import os
from datetime import datetime

# --- CONFIGURAZIONE CENTRALE OPERATIVA GLOBALE ---
# Monitoraggio delle fonti più affidabili e prestigiose del pianeta
FEEDS = [
    # ITALIA (Fonti primarie)
    "https://www.ansa.it/sito/notizie/cultura/cultura_rss.xml",
    "https://www.corriere.it/rss/cultura.xml",
    "https://www.repubblica.it/rss/spettacoli_e_cultura/rss2.0.xml",
    
    # USA & INTERNATIONAL (Global reach)
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.reutersagency.com/feed/",
    "http://rss.cnn.com/rss/edition_world.rss",
    "https://www.washingtonpost.com/arcio/rss/category/world/",
    
    # UK (Approfondimenti)
    "https://www.theguardian.com/world/rss",
    
    # FRANCIA (Testate storiche)
    "https://www.lemonde.fr/rss/une.xml",
    "https://www.lefigaro.fr/rss/figaro/culture.xml",
    
    # SPAGNA (Mondo ispanico)
    "https://elpais.com/rss/elpais/in_english.xml",
    "https://elpais.com/rss/cultura/portada.xml",
    "https://e00-elmundo.uecdn.es/elmundo/rss/cultura.xml",
    
    # GERMANIA (Europa Centrale)
    "https://rss.dw.com/xml/rss-en-world",
    "https://www.spiegel.de/schlagzeilen/index.rss",
    
    # DANIMARCA (Nord Europa)
    "https://www.dr.dk/nyheder/service/feeds/allenyheder",
    
    # GIAPPONE (Asia - Fonti in inglese per maggiore precisione nello scraping)
    "https://www.japantimes.co.jp/feed/",
    "https://www3.nhk.or.jp/nhkworld/rss/world.xml",
    
    # CINA & ASIA PACIFICO
    "https://www.scmp.com/rss/2/feed.xml", # South China Morning Post
    
    # BRASILE / PORTOGALLO
    "https://g1.globo.com/dynamo/mundo/rss2.xml"
]

# Parole chiave multilingua per intercettare i decessi
# Copre: IT, EN, FR, ES, DE, DK, PT, SE
KEYWORDS = [
    "morto", "morta", "deceduto", "deceduta", "addio a", "scomparsa", "scomparso", # IT
    "died", "passed away", "death of", "obituary", "dies at", "rest in peace",      # EN
    "est décédé", "est décédée", "mort de", "disparition de",                     # FR
    "muere", "ha muerto", "fallece", "fallecimiento", "defunción",                # ES
    "gestorben", "tot", "nachruf", "verstorben",                                  # DE
    "død", "afgået ved døden", "dødsfald",                                        # DK
    "morre", "falecimento", "faleceu",                                            # PT
    "död", "avliden"                                                              # SE
]

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_GlobalSentinel/2.0 (https://github.com/Gimmons1)'}

def get_wikipedia_details(name, lang="it"):
    """Recupera dettagli da Wikipedia cercando di mappare la lingua corretta"""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
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
    print(f"--- Sentinel Globale Attiva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # Caricamento database
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
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.title.lower()
                
                if any(key in title for key in KEYWORDS):
                    # Pulizia avanzata del nome dal titolo
                    potential_name = entry.title.split(":")[0].split("-")[0].split("(")[0]
                    potential_name = potential_name.replace("Addio a ", "").replace("Morto ", "").replace("Morta ", "").replace("Died ", "").strip()
                    
                    if potential_name.lower() not in existing_names and len(potential_name) > 3:
                        # Rilevamento lingua dinamico basato sull'origine del feed
                        lang = "en" # Default globale
                        if "ansa" in feed_url or "corriere" in feed_url or "repubblica" in feed_url: lang = "it"
                        elif "lemonde" in feed_url or "lefigaro" in feed_url: lang = "fr"
                        elif "elpais" in feed_url or "elmundo" in feed_url: lang = "es"
                        elif "spiegel" in feed_url or "dw.com" in feed_url: lang = "de"
                        elif "dr.dk" in feed_url: lang = "da"
                        elif "globo" in feed_url: lang = "pt"
                        
                        info = get_wikipedia_details(potential_name, lang)
                        if info and info["slug"]:
                            source_name = feed_url.split("/")[2].replace("www.", "")
                            new_person = {
                                "name": potential_name,
                                "slugs": {"IT": info["slug"], "EN": info["slug"]},
                                "bio": info["bio"] + f" [Rilevato da {source_name}]",
                                "birthDate": "1900-01-01",
                                "deathDate": datetime.now().strftime("%Y-%m-%d"),
                                "imageUrl": info["img"]
                            }
                            new_entries.append(new_person)
                            existing_names.append(potential_name.lower())
                            print(f" > Rilevato: {potential_name} ({lang})")
        except Exception as e:
            print(f" ! Errore durante la lettura di {feed_url}: {e}")

    if new_entries:
        library.extend(new_entries)
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"--- Scansione completata: {len(new_entries)} novità trovate ---")
    else:
        print("--- Scansione completata: Nessuna nuova notizia rilevata ---")

if __name__ == "__main__":
    run_updater()
