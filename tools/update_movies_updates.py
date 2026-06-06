import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("movies_updates.json")
TOKEN = os.environ.get("TMDB_READ_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("TMDB_READ_TOKEN is empty. Add it in GitHub: Settings -> Secrets and variables -> Actions.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "MovieCatalogTV GitHub updater",
    "Accept": "application/json"
}

IMG = "https://image.tmdb.org/t/p/w342"

def get_json(path, params=None):
    base = "https://api.themoviedb.org/3"
    params = params or {}
    params.setdefault("language", "ru-RU")
    url = base + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def genre_maps():
    maps = {"movie": {}, "tv": {}}
    for kind in ("movie", "tv"):
        data = get_json(f"/genre/{kind}/list")
        maps[kind] = {g["id"]: g["name"] for g in data.get("genres", [])}
    return maps

def load_existing():
    if not OUT.exists():
        return {"version": 1, "movies": []}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"version": 1, "movies": data}
        if "movies" not in data:
            data["movies"] = data.get("items") or data.get("anime") or []
        return data
    except Exception:
        return {"version": 1, "movies": []}

def convert_movie(item, gmap):
    title = item.get("title") or item.get("name") or ""
    original = item.get("original_title") or item.get("original_name") or title
    date = item.get("release_date") or ""
    year = date[:4] if date else ""
    poster = IMG + item["poster_path"] if item.get("poster_path") else ""

    genres = [gmap.get(x, "") for x in item.get("genre_ids", [])]
    genres = [x for x in genres if x]

    return {
        "id": 7000000 + int(item.get("id", 0)),
        "ru": title,
        "en": original,
        "year": year,
        "type": "Фильм",
        "episodes": "",
        "status": "Вышел",
        "studio": "",
        "rating": item.get("vote_average") or 0,
        "poster": poster,
        "genres": genres
    }

def convert_tv(item, gmap):
    title = item.get("name") or item.get("title") or ""
    original = item.get("original_name") or item.get("original_title") or title
    date = item.get("first_air_date") or ""
    year = date[:4] if date else ""
    poster = IMG + item["poster_path"] if item.get("poster_path") else ""

    genres = [gmap.get(x, "") for x in item.get("genre_ids", [])]
    genres = [x for x in genres if x]

    return {
        "id": 8000000 + int(item.get("id", 0)),
        "ru": title,
        "en": original,
        "year": year,
        "type": "Сериал",
        "episodes": "",
        "status": "Онгоинг",
        "studio": "",
        "rating": item.get("vote_average") or 0,
        "poster": poster,
        "genres": genres
    }

def main():
    existing = load_existing()
    movies = existing.get("movies") or []
    known = set()
    for x in movies:
        known.add(str(x.get("id", "")))
        known.add(((x.get("ru") or "") + "|" + (x.get("en") or "") + "|" + (x.get("year") or "")).lower())

    gm = genre_maps()
    added = []

    requests = [
        ("movie", "/trending/movie/week", {}, convert_movie),
        ("movie", "/movie/now_playing", {"region": "RU"}, convert_movie),
        ("movie", "/movie/popular", {"region": "RU"}, convert_movie),
        ("movie", "/movie/upcoming", {"region": "RU"}, convert_movie),
        ("tv", "/trending/tv/week", {}, convert_tv),
        ("tv", "/tv/popular", {}, convert_tv),
        ("tv", "/tv/on_the_air", {}, convert_tv),
    ]

    for kind, path, params, conv in requests:
        data = get_json(path, params)
        for item in data.get("results", [])[:30]:
            x = conv(item, gm[kind])
            if not x["ru"] and not x["en"]:
                continue
            k1 = str(x["id"])
            k2 = ((x.get("ru") or "") + "|" + (x.get("en") or "") + "|" + (x.get("year") or "")).lower()
            if k1 not in known and k2 not in known:
                movies.append(x)
                added.append(x)
                known.add(k1)
                known.add(k2)
        time.sleep(0.7)

    def sort_key(x):
        try:
            year = int(x.get("year") or 0)
        except Exception:
            year = 0
        return (year, float(x.get("rating") or 0), int(x.get("id") or 0))

    movies.sort(key=sort_key, reverse=True)

    result = {
        "version": int(existing.get("version", 1)) + (1 if added else 0),
        "movies": movies
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Added: {len(added)}")
    for x in added[:30]:
        print("-", x.get("type"), x.get("ru") or x.get("en"), x.get("year"))

if __name__ == "__main__":
    main()
