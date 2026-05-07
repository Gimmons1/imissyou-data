import os
import json
import requests
import urllib.parse
from datetime import datetime

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_Processor/2.0 (https://github.com/Gimmons1)'}

def fetch_wikipedia_data(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(name.replace(' ', '_'))}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def fetch_wikidata_dates(title, lang="it"):
    # Usa l'URL esatto di Wikipedia per trovare l'elemento perfetto su Wikidata senza ambiguità
    wiki_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
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
                b = bindings[0].get('birthDate', {}).get('value', '1900-01-01')
                d = bindings[0].get('deathDate', {}).get('value', '2000-01-01')
                
                # Estrae solo YYYY-MM-DD
                b_clean = b.split('T')[0] if 'T' in b else b
                d_clean = d.split('T')[0] if 'T' in d else d
                
                # Pulisce eventuali simboli strani di Wikidata (es. +1907-02-02)
                b_clean = b_clean.replace('+', '').strip()
                d_clean = d_clean.replace('+', '').strip()
                
                return b_clean, d_clean
    except Exception as e:
        print(f"Errore Wikidata: {e}")
        
    return "1900-01-01", "2000-01-01"

def process_issue():
    issue_title = os.getenv("ISSUE_TITLE", "")
    if not issue_title:
        return

    # Carica il database fresco
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    modified = False

    # --- LOGICA APPROVAZIONE (SINGOLA O MULTIPLA) ---
    if issue_title.startswith("APPROVE"):
        content = issue_title.replace("APPROVE: ", "").replace("APPROVE_BULK: ", "").strip()
        if issue_title == "APPROVE_ALL":
            for p in library:
                if not p.get("approved", True):
                    p["approved"] = True
                    modified = True
        else:
            names_to_approve = [n.strip().lower() for n in content.split("|")]
            for p in library:
                if p["name"].lower().strip() in names_to_approve:
                    p["approved"] = True
                    modified = True
                    print(f"✅ Approvato: {p['name']}")

    # --- LOGICA ELIMINAZIONE ---
    elif issue_title.startswith("DELETE"):
        content = issue_title.replace("DELETE: ", "").replace("DELETE_BULK: ", "").strip()
        names_to_delete = [n.strip().lower() for n in content.split("|")]
        
        new_library = []
        for p in library:
            name_low = p["name"].lower().strip()
            if name_low in names_to_delete:
                names_to_delete.remove(name_low)
                modified = True
                print(f"🗑️ Eliminata scheda: {p['name']}")
                continue
            new_library.append(p)
        library = new_library

    # --- LOGICA RICHIESTA UTENTE / ADMIN ---
    elif issue_title.startswith("USER_REQUEST:") or issue_title.startswith("ADMIN_REQUEST:"):
        is_admin = issue_title.startswith("ADMIN_REQUEST:")
        name = issue_title.split(":", 1)[1].strip()
        
        # Controllo anti-doppioni base
        if not any(p["name"].lower() == name.lower() for p in library):
            wiki_data = fetch_wikipedia_data(name)
            if wiki_data:
                real_title = wiki_data.get("titles", {}).get("canonical", name)
                bio = wiki_data.get("extract", "Biografia non disponibile.")
                img = wiki_data.get("originalimage", {}).get("source", None)
                birth, death = fetch_wikidata_dates(real_title)
                
                library.append({
                    "name": real_title,
                    "slugs": {"IT": real_title.replace(' ', '_'), "EN": real_title.replace(' ', '_')},
                    "bio": bio,
                    "birthDate": birth,
                    "deathDate": death,
                    "imageUrl": img,
                    "approved": is_admin
                })
                modified = True
                print(f"➕ Aggiunto: {real_title} (Approvato: {is_admin})")

    # Salva solo se è stato cambiato qualcosa
    if modified:
        # Ordina sempre il database per data di morte (dal più antico al più recente)
        library.sort(key=lambda x: x.get('deathDate', '2000-01-01'))
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print("💾 Database salvato con successo.")
    else:
        print("ℹ️ Nessuna modifica necessaria per questa richiesta.")

if __name__ == "__main__":
    process_issue()
