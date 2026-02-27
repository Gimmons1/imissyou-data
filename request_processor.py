import requests
import json
import os
import sys
import urllib.parse
from datetime import datetime

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_Core/6.0 (https://github.com/Gimmons1)'}

def suggest_correct_name(query, lang="it"):
    url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=1&format=json"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if len(data) > 1 and len(data[1]) > 0:
                return data[1][0]
    except: pass
    return None

def fetch_wikipedia_data(name, lang="it"):
    slug = name.replace(' ', '_')
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "extract" in data and len(data["extract"]) > 30 and data.get("type") != "disambiguation":
                return data
    except: pass
    return None

def fetch_wikidata_dates(slug, lang="it"):
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
                b = bindings[0].get('birthDate', {}).get('value', '1900-01-01').split('T')[0]
                # SE NON HA UNA DATA DI MORTE, È VIVO (restituisco None)
                d = bindings[0].get('deathDate', {}).get('value')
                if d:
                    return b, d.split('T')[0]
                else:
                    return b, None
    except: pass
    return "1900-01-01", None

def run_processor():
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if not issue_title: return

    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    # COMANDO: APPROVA TUTTE LE SCHEDE IN ATTESA IN UN COLPO SOLO
    if issue_title.startswith("APPROVE_ALL"):
        for p in library:
            if not p.get("approved", True):
                p["approved"] = True
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print("✅ Approvate tutte le schede in attesa.")
        return

    # COMANDO: ELIMINA o RIFIUTA
    if issue_title.startswith("DELETE: "):
        name_to_del = issue_title.replace("DELETE: ", "").strip().lower()
        name_to_del_alt = name_to_del.replace(" ", "_")
        
        # Elimina anche se ci sono le diciture "⚠️ ERRORE" o "⛔ ANCORA IN VITA"
        name_to_del_clean = name_to_del.replace("⚠️ errore: ", "").replace("⛔ ancora in vita: ", "")
        
        original_count = len(library)
        library = [p for p in library if 
                   p["name"].lower() != name_to_del and 
                   p["name"].lower() != name_to_del_alt and
                   p["name"].lower() != f"⚠️ errore: {name_to_del_clean}" and
                   p["name"].lower() != f"⛔ ancora in vita: {name_to_del_clean}"]
        
        if len(library) < original_count:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: APPROVA SINGOLA RICHIESTA UTENTE
    if issue_title.startswith("APPROVE: "):
        name_to_approve = issue_title.replace("APPROVE: ", "").strip().lower()
        found = False
        for p in library:
            if p["name"].lower() == name_to_approve or p["name"].lower() == name_to_approve.replace(" ", "_"):
                p["approved"] = True
                found = True
                break
        if found:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: AGGIUNGI (Admin o Utente)
    is_admin = issue_title.startswith("ADMIN_REQUEST: ")
    is_user = issue_title.startswith("USER_REQUEST: ")

    if is_admin or is_user:
        prefix = "ADMIN_REQUEST: " if is_admin else "USER_REQUEST: "
        name_to_add = issue_title.replace(prefix, "").strip()
        
        wiki_data = fetch_wikipedia_data(name_to_add, "it")
        lang_used = "it"
        if not wiki_data:
            wiki_data = fetch_wikipedia_data(name_to_add, "en")
            lang_used = "en"
            
        if not wiki_data:
            suggested = suggest_correct_name(name_to_add, "it") or suggest_correct_name(name_to_add, "en")
            if suggested:
                wiki_data = fetch_wikipedia_data(suggested, "it")
                lang_used = "it"
                if not wiki_data:
                    wiki_data = fetch_wikipedia_data(suggested, "en")
                    lang_used = "en"

        if not wiki_data:
            library.append({
                "name": f"⚠️ ERRORE: {name_to_add}",
                "slugs": {"IT": "", "EN": ""},
                "bio": "ATTENZIONE ADMIN: Il server non ha trovato nessuna pagina Wikipedia per questo nome. Usa il cestino rosso per eliminare questa scheda.",
                "birthDate": "1900-01-01",
                "deathDate": datetime.now().strftime("%Y-%m-%d"),
                "imageUrl": None,
                "approved": False 
            })
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            sys.exit(0)

        raw_title = wiki_data.get("title", name_to_add)
        real_title = raw_title.replace("_", " ") 
        slug = wiki_data.get("titles", {}).get("canonical", raw_title)

        for p in library:
            if p["name"].lower() == real_title.lower() or p["slugs"].get("EN", "").lower() == slug.lower() or p["slugs"].get("IT", "").lower() == slug.lower():
                return

        birth, death = fetch_wikidata_dates(slug, lang_used)
        
        # CROSS-CHECK VITA/MORTE RIGOROSO SULLE FONTI AFFIDABILI
        if not death:
            print(f"❌ BLOCCATO: {real_title} risulta in vita!")
            library.append({
                "name": f"⛔ ANCORA IN VITA: {real_title}",
                "slugs": {"IT": "", "EN": ""},
                "bio": "CROSS-CHECK FALLITO: Secondo i dati incrociati mondiali (Wikidata), questa persona è attualmente in vita. La scheda non può essere pubblicata nell'App. Eliminala usando il cestino rosso.",
                "birthDate": birth,
                "deathDate": datetime.now().strftime("%Y-%m-%d"),
                "imageUrl": wiki_data.get("originalimage", {}).get("source", None),
                "approved": False 
            })
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            sys.exit(0)
        
        library.append({
            "name": real_title,
            "slugs": {"IT": slug, "EN": slug},
            "bio": wiki_data.get("extract", "Biografia non disponibile."),
            "birthDate": birth,
            "deathDate": death,
            "imageUrl": wiki_data.get("originalimage", {}).get("source", None),
            "approved": is_admin
        })
        
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_processor()
