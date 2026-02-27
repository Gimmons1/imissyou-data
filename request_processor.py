import requests
import json
import os
import sys
import urllib.parse
from datetime import datetime

# File di database locale
JSON_FILE = "library.json"

# Intestazioni per identificare le richieste e rispettare le policy di Wikipedia/Wikidata
HEADERS = {
    'User-Agent': 'iMissYouApp_Core/9.5 (https://github.com/Gimmons1)',
    'Accept': 'application/json'
}

def search_wikipedia_titles(query, lang="it"):
    """Cerca fino a 8 titoli corrispondenti su Wikipedia per gestire omonimi e varianti."""
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=8"
    titles = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            for item in data.get("query", {}).get("search", []):
                titles.append(item["title"])
    except Exception as e:
        print(f"Errore ricerca titoli: {e}")
    return titles

def fetch_wikipedia_data(name, lang="it"):
    """Recupera il riassunto della biografia e l'immagine ufficiale."""
    slug = name.replace(' ', '_')
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # Accettiamo solo se c'è un estratto significativo e non è una pagina di disambiguazione
            if "extract" in data and len(data["extract"]) > 30 and data.get("type") != "disambiguation":
                return data
    except Exception as e:
        print(f"Errore fetch Wikipedia: {e}")
    return None

def fetch_wikidata_dates(slug, lang="it"):
    """
    Esegue il cross-check su Wikidata per ottenere date di nascita e morte.
    Gestisce correttamente date antiche (es. Mozart 1791) e formati SPARQL.
    """
    wiki_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(slug)}"
    query = f"""
    SELECT ?birthDate ?deathDate WHERE {{
      <{wiki_url}> schema:about ?item .
      OPTIONAL {{ ?item wdt:P569 ?birthDate . }}
      OPTIONAL {{ ?item wdt:P570 ?deathDate . }}
    }} LIMIT 1
    """
    try:
        res = requests.get("https://query.wikidata.org/sparql", params={'query': query, 'format': 'json'}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            bindings = res.json()['results']['bindings']
            if bindings:
                # Wikidata può restituire date con il prefisso '+' per anni antichi
                b_raw = bindings[0].get('birthDate', {}).get('value', '1000-01-01')
                d_raw = bindings[0].get('deathDate', {}).get('value')
                
                # Pulizia stringhe: estraiamo solo YYYY-MM-DD
                birth = b_raw.split('T')[0].replace('+', '')
                death = d_raw.split('T')[0].replace('+', '') if d_raw else None
                return birth, death
    except Exception as e:
        print(f"Errore cross-check Wikidata: {e}")
    return "1000-01-01", None

def run_processor():
    # Recupera il titolo del Ticket aperto dall'App
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if not issue_title:
        print("Nessun comando ricevuto.")
        return

    # Caricamento database esistente
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                library = json.load(f)
            except:
                library = []
    
    # 1. GESTIONE COMANDI BULK (Approvazione o Eliminazione multipla)
    if issue_title.startswith("APPROVE_BULK: "):
        names = issue_title.replace("APPROVE_BULK: ", "").split("|")
        names = [n.strip().lower() for n in names]
        for p in library:
            if p["name"].lower() in names:
                p["approved"] = True
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ Approvate in blocco: {len(names)} persone.")
        return

    if issue_title.startswith("DELETE_BULK: "):
        names = issue_title.replace("DELETE_BULK: ", "").split("|")
        names = [n.strip().lower() for n in names]
        library = [p for p in library if p["name"].lower() not in names]
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"🗑️ Eliminate in blocco: {len(names)} persone.")
        return

    # 2. GESTIONE RICHIESTE DI AGGIUNTA (Admin o Utente)
    prefix = ""
    if issue_title.startswith("ADMIN_REQUEST: "): prefix = "ADMIN_REQUEST: "
    elif issue_title.startswith("USER_REQUEST: "): prefix = "USER_REQUEST: "
    
    if prefix:
        name_query = issue_title.replace(prefix, "").strip()
        print(f"Elaborazione richiesta per: {name_query}")
        
        # Cerchiamo omonimi sia in italiano che in inglese
        candidates = search_wikipedia_titles(name_query, "it") + search_wikipedia_titles(name_query, "en")
        unique_titles = list(set([name_query] + candidates))
        
        added_count = 0
        
        for t in unique_titles:
            # Proviamo a scaricare i dati (preferenza Italiano, poi Inglese)
            data = fetch_wikipedia_data(t, "it") or fetch_wikipedia_data(t, "en")
            if not data:
                continue
                
            real_name = data.get("title", t).replace("_", " ")
            slug = data.get("titles", {}).get("canonical", t)
            
            # Evitiamo doppioni nel database
            if any(p["name"].lower() == real_name.lower() for p in library):
                print(f"-> {real_name} è già presente.")
                continue

            # Cross-check date su Wikidata
            birth, death = fetch_wikidata_dates(slug)
            
            # Se Wikidata dice che è vivo (death è None), blocchiamo
            if not death:
                if t.lower() == name_query.lower():
                    print(f"-> BLOCCO: {real_name} risulta ancora in vita.")
                    library.append({
                        "name": f"⛔ ANCORA IN VITA: {real_name}",
                        "slugs": {"IT": "", "EN": ""},
                        "bio": "Questa persona risulta essere ancora in vita secondo i database mondiali. La scheda non può essere pubblicata.",
                        "birthDate": birth,
                        "deathDate": datetime.now().strftime("%Y-%m-%d"),
                        "approved": False
                    })
                continue
                
            # Aggiungiamo la persona deceduta
            library.append({
                "name": real_name,
                "slugs": {"IT": slug, "EN": slug},
                "bio": data.get("extract", "Biografia non disponibile."),
                "birthDate": birth,
                "deathDate": death,
                "imageUrl": data.get("originalimage", {}).get("source"),
                "approved": "ADMIN" in prefix # Gli admin pubblicano subito, gli utenti vanno in attesa
            })
            added_count += 1
            print(f"-> AGGIUNTO: {real_name} ({birth} - {death})")
            
        if added_count > 0:
            # Ordiniamo il database per data di morte
            library.sort(key=lambda x: x['deathDate'])
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            print(f"Database salvato con {added_count} nuovi inserimenti.")
        else:
            # Se proprio non troviamo nulla, creiamo un log di errore visibile nell'app
            if not any(name_query.lower() in p["name"].lower() for p in library):
                library.append({
                    "name": f"⚠️ ERRORE: {name_query}",
                    "slugs": {"IT": "", "EN": ""},
                    "bio": "Nessuna corrispondenza trovata su Wikipedia o Wikidata per questo nome.",
                    "birthDate": "1000-01-01",
                    "deathDate": datetime.now().strftime("%Y-%m-%d"),
                    "approved": False
                })
                with open(JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump(library, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_processor()
