import requests
import json
import os
import sys
import urllib.parse
from datetime import datetime

JSON_FILE = "library.json"
ANALYTICS_FILE = "analytics.json"

HEADERS = {
    'User-Agent': 'iMissYouApp_Core/10.2 (https://github.com/Gimmons1)',
    'Accept': 'application/json'
}

def search_wikipedia_titles(query, lang="it"):
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=8"
    titles = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            for item in res.json().get("query", {}).get("search", []): titles.append(item["title"])
    except: pass
    return titles

def fetch_wikipedia_data(name, lang="it"):
    slug = name.replace(' ', '_')
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "extract" in data and len(data["extract"]) > 30 and data.get("type") != "disambiguation": return data
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
                b_raw = bindings[0].get('birthDate', {}).get('value', '1000-01-01')
                d_raw = bindings[0].get('deathDate', {}).get('value')
                return b_raw.split('T')[0].replace('+', ''), d_raw.split('T')[0].replace('+', '') if d_raw else None
    except: pass
    return "1000-01-01", None

def run_processor():
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if not issue_title: return

    # 1. GESTIONE ANALYTICS (Tracciamento del tempo)
    if issue_title.startswith("VIEW: "):
        # Il formato in arrivo dall'app è: "VIEW: Nome | Secondi"
        parts = issue_title.replace("VIEW: ", "").split("|")
        viewed_name = parts[0].strip()
        duration = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 0
        
        print(f"📊 Registrazione per: {viewed_name} (Tempo: {duration}s)")
        
        analytics = {}
        if os.path.exists(ANALYTICS_FILE):
            try:
                with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                    analytics = json.load(f)
            except: pass
            
        # Retrocompatibilità se il file è vecchio
        if viewed_name in analytics and isinstance(analytics[viewed_name], int):
            old_views = analytics[viewed_name]
            analytics[viewed_name] = {"views": old_views, "time": 0}
            
        if viewed_name not in analytics:
            analytics[viewed_name] = {"views": 0, "time": 0}
            
        # Aggiorna i contatori
        analytics[viewed_name]["views"] += 1
        analytics[viewed_name]["time"] += duration
        
        with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
            json.dump(analytics, f, indent=2, ensure_ascii=False)
        print("📊 Analytics salvate con successo.")
        return 

    # 2. GESTIONE DATABASE TRADIZIONALE
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: pass
    
    if issue_title.startswith("APPROVE_BULK: "):
        names = [n.strip().lower() for n in issue_title.replace("APPROVE_BULK: ", "").split("|")]
        for p in library:
            if p["name"].lower() in names: p["approved"] = True
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(library, f, indent=2, ensure_ascii=False)
        return

    if issue_title.startswith("DELETE_BULK: "):
        names = [n.strip().lower() for n in issue_title.replace("DELETE_BULK: ", "").split("|")]
        new_library = []
        for p in library:
            name_lower = p["name"].lower()
            if name_lower in names:
                names.remove(name_lower) # Rimuove solo un'istanza alla volta dalla lista di bersagli
                continue
            new_library.append(p)
        library = new_library
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(library, f, indent=2, ensure_ascii=False)
        return

    prefix = ""
    if issue_title.startswith("ADMIN_REQUEST: "): prefix = "ADMIN_REQUEST: "
    elif issue_title.startswith("USER_REQUEST: "): prefix = "USER_REQUEST: "
    elif issue_title.startswith("APPROVE: "):
        name_to_approve = issue_title.replace("APPROVE: ", "").strip()
        for p in library:
            if p["name"].lower() == name_to_approve.lower(): p["approved"] = True
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(library, f, indent=2, ensure_ascii=False)
        return
    elif issue_title.startswith("DELETE: "):
        name_to_delete = issue_title.replace("DELETE: ", "").strip()
        new_library = []
        deleted = False
        for p in library:
            # Se trova una corrispondenza e non l'ha ancora cancellata, la salta (quindi la elimina)
            if not deleted and p["name"].lower() == name_to_delete.lower():
                deleted = True 
                continue
            new_library.append(p)
        library = new_library
        with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(library, f, indent=2, ensure_ascii=False)
        return
    
    if prefix:
        name_query = issue_title.replace(prefix, "").strip()
        candidates = search_wikipedia_titles(name_query, "it") + search_wikipedia_titles(name_query, "en")
        unique_titles = list(set([name_query] + candidates))
        added_count = 0
        
        for t in unique_titles:
            data = fetch_wikipedia_data(t, "it") or fetch_wikipedia_data(t, "en")
            if not data: continue
            real_name = data.get("title", t).replace("_", " ")
            slug = data.get("titles", {}).get("canonical", t)
            
            if any(p["name"].lower() == real_name.lower() for p in library): continue
            birth, death = fetch_wikidata_dates(slug)
            
            if not death:
                if t.lower() == name_query.lower():
                    library.append({"name": f"⛔ ANCORA IN VITA: {real_name}", "slugs": {"IT": "", "EN": ""}, "bio": "Questa persona risulta essere ancora in vita.", "birthDate": birth, "deathDate": datetime.now().strftime("%Y-%m-%d"), "approved": False})
                continue
                
            library.append({"name": real_name, "slugs": {"IT": slug, "EN": slug}, "bio": data.get("extract", "Biografia non disponibile."), "birthDate": birth, "deathDate": death, "imageUrl": data.get("originalimage", {}).get("source"), "approved": "ADMIN" in prefix})
            added_count += 1
            
        if added_count > 0:
            library.sort(key=lambda x: x['deathDate'])
            with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(library, f, indent=2, ensure_ascii=False)
        else:
            if not any(name_query.lower() in p["name"].lower() for p in library):
                library.append({"name": f"⚠️ ERRORE: {name_query}", "slugs": {"IT": "", "EN": ""}, "bio": "Nessuna corrispondenza trovata.", "birthDate": "1000-01-01", "deathDate": datetime.now().strftime("%Y-%m-%d"), "approved": False})
                with open(JSON_FILE, "w", encoding="utf-8") as f: json.dump(library, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_processor()
