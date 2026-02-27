import requests
import json
import os
import sys
import urllib.parse
from datetime import datetime

JSON_FILE = "library.json"
# Fonti certificate
HEADERS = {'User-Agent': 'iMissYouApp_Core/7.0 (https://github.com/Gimmons1)'}

def search_wikipedia_titles(query, lang="it"):
    # Usa l'API di ricerca di Wikipedia per trovare fino a 4 omonimi famosi
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=4"
    titles = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            for item in data.get("query", {}).get("search", []):
                titles.append(item["title"])
    except: pass
    return titles

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

    # COMANDO: APPROVA MULTIPLA
    if issue_title.startswith("APPROVE_BULK: "):
        names_to_approve = issue_title.replace("APPROVE_BULK: ", "").split("|")
        names_to_approve = [n.strip().lower() for n in names_to_approve]
        found = False
        for p in library:
            name_clean = p["name"].lower()
            name_alt = name_clean.replace(" ", "_")
            if name_clean in names_to_approve or name_alt in names_to_approve:
                p["approved"] = True
                found = True
        if found:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: ELIMINA MULTIPLA
    if issue_title.startswith("DELETE_BULK: "):
        names_to_del = issue_title.replace("DELETE_BULK: ", "").split("|")
        names_to_del = [n.strip().lower() for n in names_to_del]
        original_count = len(library)
        new_library = []
        for p in library:
            p_name = p["name"].lower()
            match = False
            for target in names_to_del:
                target_clean = target.replace("⚠️ errore: ", "").replace("⛔ ancora in vita: ", "")
                if p_name == target or p_name == target.replace(" ", "_") or p_name == f"⚠️ errore: {target_clean}" or p_name == f"⛔ ancora in vita: {target_clean}":
                    match = True
                    break
            if not match:
                new_library.append(p)
        if len(new_library) < original_count:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(new_library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: APPROVA SINGOLA
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

    # COMANDO: ELIMINA SINGOLA
    if issue_title.startswith("DELETE: "):
        name_to_del = issue_title.replace("DELETE: ", "").strip().lower()
        name_to_del_alt = name_to_del.replace(" ", "_")
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

    # COMANDO: APPROVA TUTTE
    if issue_title.startswith("APPROVE_ALL"):
        for p in library:
            if not p.get("approved", True):
                p["approved"] = True
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: AGGIUNGI (Cerca omonimi ed esegue il cross-check su tutti)
    is_admin = issue_title.startswith("ADMIN_REQUEST: ")
    is_user = issue_title.startswith("USER_REQUEST: ")

    if is_admin or is_user:
        prefix = "ADMIN_REQUEST: " if is_admin else "USER_REQUEST: "
        name_to_add = issue_title.replace(prefix, "").strip()
        
        # Cerca i nomi potenziali (incluso l'omonimia)
        candidates_it = search_wikipedia_titles(name_to_add, "it")
        candidates_en = search_wikipedia_titles(name_to_add, "en")
        
        titles_it = []
        for t in [name_to_add] + candidates_it:
            if t.lower() not in [x.lower() for x in titles_it]: titles_it.append(t)
            
        titles_en = []
        for t in [name_to_add] + candidates_en:
            if t.lower() not in [x.lower() for x in titles_en]: titles_en.append(t)

        added_anyone = False
        alive_found = False
        alive_name = ""

        # Setaccia tutti gli omonimi trovati
        for lang, titles in [("it", titles_it), ("en", titles_en)]:
            for title in titles:
                wiki_data = fetch_wikipedia_data(title, lang)
                if not wiki_data: continue

                raw_title = wiki_data.get("title", title)
                real_title = raw_title.replace("_", " ") 
                slug = wiki_data.get("titles", {}).get("canonical", raw_title)

                # Verifica se questo specifico omonimo è già nel database
                already_exists = False
                for p in library:
                    if p["name"].lower() == real_title.lower() or p["slugs"].get("EN", "").lower() == slug.lower() or p["slugs"].get("IT", "").lower() == slug.lower():
                        already_exists = True
                        break
                if already_exists:
                    continue 

                birth, death = fetch_wikidata_dates(slug, lang)
                
                # CROSS CHECK: Se non c'è una data di morte, è vivo!
                if not death:
                    if title.lower() == name_to_add.lower() or real_title.lower() == name_to_add.lower():
                        alive_found = True
                        alive_name = real_title
                    continue
                    
                # È MORTO ED È FAMOSO! Lo estraiamo.
                slug_dict = {"IT": slug, "EN": slug}
                if lang == "it": slug_dict["EN"] = ""
                else: slug_dict["IT"] = ""
                    
                library.append({
                    "name": real_title,
                    "slugs": slug_dict,
                    "bio": wiki_data.get("extract", "Biografia non disponibile."),
                    "birthDate": birth,
                    "deathDate": death,
                    "imageUrl": wiki_data.get("originalimage", {}).get("source", None),
                    "approved": is_admin
                })
                added_anyone = True

        # Se non abbiamo trovato NESSUN morto tra tutti gli omonimi indagati
        if not added_anyone:
            if alive_found:
                library.append({
                    "name": f"⛔ ANCORA IN VITA: {alive_name}",
                    "slugs": {"IT": "", "EN": ""},
                    "bio": "CROSS-CHECK FALLITO: Secondo i dati mondiali (Wikidata), questa persona è in vita e non sono stati trovati omonimi deceduti. Usa il cestino rosso per rimuovere questa scheda.",
                    "birthDate": "1900-01-01",
                    "deathDate": datetime.now().strftime("%Y-%m-%d"),
                    "imageUrl": None,
                    "approved": False 
                })
            else:
                library.append({
                    "name": f"⚠️ ERRORE: {name_to_add}",
                    "slugs": {"IT": "", "EN": ""},
                    "bio": "ATTENZIONE ADMIN: Il server non ha trovato nessuna persona celebre deceduta corrispondente a questo nome (né tra i suoi omonimi). Elimina questa scheda col cestino.",
                    "birthDate": "1900-01-01",
                    "deathDate": datetime.now().strftime("%Y-%m-%d"),
                    "imageUrl": None,
                    "approved": False 
                })
        
        # Scrive il file salvando tutti i nuovi omonimi
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        sys.exit(0)

if __name__ == "__main__":
    run_processor()
