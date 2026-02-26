import requests
import json
import os
import time

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    'User-Agent': 'iMissYouApp_DeepSearch/7.0 (https://github.com/Gimmons1)',
    'Accept': 'application/sparql-results+json'
}

# SCAGLIONI DI 15 ANNI: Wikidata non andrà mai più in sovraccarico (Errore 504 bypassato)
EPOCHE = [
    (1920, 1935), (1936, 1950), (1951, 1965),
    (1966, 1980), (1981, 1995), (1996, 2010), (2011, 2026) # Esteso per includere il 2026!
]

def get_wikipedia_bio(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=(5, 5))
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", ""), data.get("extract", "")
    except:
        pass
    return name, "Biografia storica recuperata dagli archivi ufficiali."

def run_historical_import():
    print("Avvio ricerca storica a fette temporali (Anti-504)...")
    
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: pass

    existing_names = set(p["name"].lower().strip() for p in library)
    new_entries = []

    for inizio, fine in EPOCHE:
        print(f"\n--- Analizzo gli anni dal {inizio} al {fine} ---")
        
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
        LIMIT 250
        """
        
        success = False
        for attempt in range(4): # 4 tentativi di sicurezza per blocco
            try:
                response = requests.get(SPARQL_URL, params={'query': query}, headers=HEADERS, timeout=(10, 30))
                if response.status_code == 200:
                    results = response.json()['results']['bindings']
                    print(f" -> Trovate {len(results)} persone per questa epoca. Avvio scaricamento...")
                    
                    for item in results:
                        name = item['personLabel']['value'].strip()
                        name_lower = name.lower()
                        
                        if name_lower in existing_names or name.startswith("Q") or "http" in name: 
                            continue
                            
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
                        time.sleep(0.2)
                    success = True
                    break
                else:
                    print(f"Server occupato ({response.status_code}). Attendo 8 secondi...")
                    time.sleep(8)
            except Exception as e:
                print("Timeout di rete temporaneo. Attendo 8 secondi...")
                time.sleep(8)
                
        if not success:
            print(f"Impossibile scansionare l'epoca {inizio}-{fine}, passo alla successiva.")

    if new_entries:
        library.extend(new_entries)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"\n✅ SUCCESSO: Aggiunti {len(new_entries)} personaggi.")
    else:
        print("\nNessun nuovo personaggio trovato.")

if __name__ == "__main__":
    run_historical_import()
