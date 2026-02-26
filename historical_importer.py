import requests
import json
import os
import time

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"

# FONDAMENTALE: I server di Wikipedia bloccano le richieste anonime. 
# Questo "Header" dice a Wikipedia che siamo un'app legittima e non ci bloccheranno.
HEADERS = {
    'User-Agent': 'iMissYouApp_DataUpdater/1.0 (https://github.com/Gimmons1) Python/3.9'
}

# Cerchiamo personaggi morti dal 1920 in poi, famosissimi (tradotti in almeno 40 lingue)
QUERY = """
SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks WHERE {
  ?person wdt:P31 wd:Q5. 
  ?person wdt:P569 ?birthDate.
  ?person wdt:P570 ?deathDate.
  OPTIONAL { ?person wdt:P18 ?image. }
  FILTER(YEAR(?deathDate) >= 1920)
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 40)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
}
ORDER BY DESC(?sitelinks)
LIMIT 100
"""

def get_wikipedia_bio(name, lang="it"):
    """Scarica la biografia da Wikipedia per completare i dati"""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        # Usa gli HEADERS anche qui!
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", ""), data.get("extract", "")
    except Exception as e:
        print(f"Impossibile scaricare biografia per {name}: {e}")
        
    return name, "Biografia storica recuperata dagli archivi."

def run_historical_import():
    print("Contattando gli archivi ufficiali di Wikidata...")
    
    # Eseguiamo la richiesta inviando la nostra identità
    response = requests.get(SPARQL_URL, params={'format': 'json', 'query': QUERY}, headers=HEADERS)
    
    # Se Wikipedia ci blocca, questa volta fermiamo lo script con un errore visibile
    if response.status_code != 200:
        raise Exception(f"❌ ERRORE SERVER WIKIDATA: {response.status_code}\n{response.text}")

    data = response.json()
    results = data['results']['bindings']
    print(f"Trovati {len(results)} personaggi storici illustri.")

    # Carica libreria esistente
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: 
                library = json.load(f)
            except: 
                pass

    existing_names = [p["name"].lower() for p in library]
    new_entries = []

    for item in results:
        name = item['personLabel']['value']
        
        # Salta se è già nel database o se il nome non è stato tradotto
        if name.lower() in existing_names or name.startswith("Q") or "http" in name: 
            continue
            
        print(f"Scaricando: {name}...")
        birth = item['birthDate']['value'].split('T')[0]
        death = item['deathDate']['value'].split('T')[0]
        img = item['image']['value'] if 'image' in item else None
        
        # Recupera la bio
        slug, bio = get_wikipedia_bio(name)
        
        new_entries.append({
            "name": name, 
            "slugs": {"IT": slug, "EN": slug},
            "bio": bio, 
            "birthDate": birth, 
            "deathDate": death, 
            "imageUrl": img
        })
        
        # Pausa obbligatoria per non sovraccaricare i server di Wikipedia ed evitare un blocco temporaneo
        time.sleep(1.0)

    # Salva il file
    if new_entries:
        library.extend(new_entries)
        # Ordina per data di morte (dal più vecchio al più recente)
        library.sort(key=lambda x: x['deathDate'])
        
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
            
        print(f"✅ SUCCESSO! Aggiunti {len(new_entries)} personaggi al file JSON.")
    else:
        print("Nessun nuovo personaggio da aggiungere.")

if __name__ == "__main__":
    run_historical_import()
