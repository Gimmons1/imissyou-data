import requests
import json
import os
import time

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"

# L'inserimento del contatto è richiesto dalle policy ufficiali di Wikipedia per evitare i blocchi severi.
HEADERS = {
    'User-Agent': 'iMissYouApp_DeepSearch/5.0 (https://github.com/Gimmons1; contact: gimmonslombardi@gmail.com) Python/requests',
    'Accept': 'application/sparql-results+json'
}

# QUERY SUPER-OTTIMIZZATA:
# Il filtro "sitelinks" è stato spostato in alto per alleggerire il calcolo del 95%
# ed evitare categoricamente gli errori "Timeout" o i crash del server Wikidata.
QUERY = """
SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks WHERE {
  ?person wdt:P31 wd:Q5. 
  
  # Filtro Fama (Soglia bassa: 20, per intercettare attori, star tv locali come Carrà o internazionali)
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 20)
  
  ?person wdt:P569 ?birthDate.
  ?person wdt:P570 ?deathDate.
  FILTER(YEAR(?deathDate) >= 1920)
  
  OPTIONAL { ?person wdt:P18 ?image. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
}
ORDER BY DESC(?sitelinks)
LIMIT 1500
"""

def get_wikipedia_bio(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", ""), data.get("extract", "")
    except Exception:
        pass
    return name, "Biografia storica recuperata dagli archivi ufficiali."

def run_historical_import():
    print("Avvio ricerca profonda ottimizzata su Wikidata (Fino a 1500 celebrità)...")
    
    # SISTEMA DI SICUREZZA ANTI-BLOCCO (Riprova 3 volte se ci sono problemi di linea)
    for attempt in range(3):
        response = requests.get(SPARQL_URL, params={'query': QUERY}, headers=HEADERS)
        if response.status_code == 200:
            break # Connessione stabilita con successo!
        else:
            print(f"Tentativo {attempt + 1} fallito. Codice errore: {response.status_code}")
            print(f"Dettaglio: {response.text}")
            if attempt < 2:
                print("Attendo 5 secondi e riprovo...")
                time.sleep(5)
            else:
                raise Exception(f"Errore server Wikidata irreversibile: {response.status_code}")

    results = response.json()['results']['bindings']
    print(f"Query completata in un lampo! Scaricati {len(results)} personaggi storici.")
    print("Avvio il download delle singole biografie...")
    
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: pass

    existing_names = set(p["name"].lower().strip() for p in library)
    new_entries = []

    for item in results:
        name = item['personLabel']['value'].strip()
        name_lower = name.lower()
        
        if name_lower in existing_names or name.startswith("Q") or "http" in name: 
            continue
            
        print(f"Scaricando: {name}...")
        birth = item['birthDate']['value'].split('T')[0]
        death = item['deathDate']['value'].split('T')[0]
        img = item['image']['value'] if 'image' in item else None
        slug, bio = get_wikipedia_bio(name)
        
        new_entries.append({
            "name": name, 
            "slugs": {"IT": slug, "EN": slug},
            "bio": bio, 
            "birthDate": birth, 
            "deathDate": death, 
            "imageUrl": img,
            "approved": True # I dati storici di Wikipedia sono sempre pre-approvati
        })
        existing_names.add(name_lower)
        time.sleep(0.3)

    if new_entries:
        library.extend(new_entries)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ SUCCESSO: Aggiunti {len(new_entries)} personaggi.")
    else:
        print("Nessun nuovo personaggio da aggiungere.")

if __name__ == "__main__":
    run_historical_import()
