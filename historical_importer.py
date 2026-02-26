import requests
import json
import os
import time

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    'User-Agent': 'iMissYouApp_DeepSearch/6.0 (https://github.com/Gimmons1; contact: gimmonslombardi@gmail.com)',
    'Accept': 'application/sparql-results+json'
}

# CHUNKING TEMPORALE: Dividiamo la ricerca in "epoche" storiche.
# Questo impedisce categoricamente l'Errore 504 (Timeout) sui server di Wikidata.
EPOCHE = [
    (1920, 1950),
    (1951, 1980),
    (1981, 2005),
    (2006, 2025)
]

def get_wikipedia_bio(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", ""), data.get("extract", "")
    except:
        pass
    return name, "Biografia storica recuperata dagli archivi ufficiali."

def run_historical_import():
    print("Avvio ricerca profonda anti-blocco a scaglioni temporali...")
    
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: pass

    existing_names = set(p["name"].lower().strip() for p in library)
    new_entries = []

    for inizio, fine in EPOCHE:
        print(f"\n--- Scansione Epoca: {inizio} - {fine} ---")
        
        query = f"""
        SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks WHERE {{
          ?person wdt:P31 wd:Q5. 
          ?person wdt:P570 ?deathDate.
          FILTER(YEAR(?deathDate) >= {inizio} && YEAR(?deathDate) <= {fine})
          
          ?person wikibase:sitelinks ?sitelinks .
          FILTER(?sitelinks >= 25)
          
          ?person wdt:P569 ?birthDate.
          OPTIONAL {{ ?person wdt:P18 ?image. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
        }}
        ORDER BY DESC(?sitelinks)
        LIMIT 400
        """
        
        success = False
        for attempt in range(3): # Riprova 3 volte in caso di micro-disconnessioni
            try:
                response = requests.get(SPARQL_URL, params={'query': query}, headers=HEADERS, timeout=30)
                if response.status_code == 200:
                    results = response.json()['results']['bindings']
                    print(f"Trovati {len(results)} VIP per questa epoca.")
                    
                    for item in results:
                        name = item['personLabel']['value'].strip()
                        name_lower = name.lower()
                        
                        if name_lower in existing_names or name.startswith("Q") or "http" in name: 
                            continue
                            
                        print(f" > Aggiungo: {name}")
                        birth = item['birthDate']['value'].split('T')[0]
                        death = item['deathDate']['value'].split('T')[0]
                        img = item['image']['value'] if 'image' in item else None
                        slug, bio = get_wikipedia_bio(name)
                        
                        new_entries.append({
                            "name": name, "slugs": {"IT": slug, "EN": slug},
                            "bio": bio, "birthDate": birth, "deathDate": death, 
                            "imageUrl": img, "approved": True
                        })
                        existing_names.add(name_lower)
                        time.sleep(0.3)
                    success = True
                    break
                else:
                    print(f"Errore server {response.status_code}. Riprovo tra 5 secondi...")
                    time.sleep(5)
            except Exception as e:
                print(f"Timeout di rete. Riprovo... ({e})")
                time.sleep(5)
                
        if not success:
            print(f"Impossibile scaricare l'epoca {inizio}-{fine}, passo alla successiva per non bloccare lo script.")

    if new_entries:
        library.extend(new_entries)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"\n✅ SUCCESSO TOTALE: Aggiunti {len(new_entries)} nuovi personaggi all'archivio.")
    else:
        print("\nNessun nuovo personaggio mancante rilevato.")

if __name__ == "__main__":
    run_historical_import()
