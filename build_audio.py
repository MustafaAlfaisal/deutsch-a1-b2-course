# -*- coding: utf-8 -*-
"""
Fetch native-speaker pronunciations for the vocabulary from German Wiktionary / Wikimedia Commons.

For every German word in course_data.json this looks up the matching de.wiktionary page, picks a
recording whose file name is that exact word (e.g. "De-Tisch.ogg"), and downloads the MP3 version
Commons generates for it into audio/. Words without a recording are left out; the app reads those
aloud with the browser's German voice instead.

Outputs:
  audio/*.mp3          one file per word (existing files are kept, so re-runs only fetch new words)
  audio/manifest.json  {"der Tisch": "tisch.mp3", ...} - loaded by index.html
  audio/credits.html   speaker + license for every recording (required by the CC licenses)
"""
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

AUDIO_DIR = "audio"
UA = "deutsch-a1-b2-course-audio-builder/1.0 (https://github.com/mustafaalfaisal/deutsch-a1-b2-course)"
WIKT_API = "https://de.wiktionary.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
AUDIO_EXT = r"\.(ogg|oga|wav|mp3|flac|opus)$"


def api(url, params):
    params = dict(params, format="json", formatversion="2")
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            # upload.wikimedia.org rate-limits bulk downloads; back off and retry
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * 2 ** attempt)
    with open(path, "wb") as f:
        f.write(data)
    time.sleep(1)


def candidates(de):
    """Wiktionary titles to try for a vocab entry, best first."""
    h = re.sub(r"^(der|die|das)\s+", "", de.strip()).rstrip("?!.").strip()
    if h.startswith("sich "):
        # reflexive verbs: the base verb's recording ("sich gewöhnen an" -> "gewöhnen")
        h = h[5:].split()[0]
    out = []
    for c in (h, h[:1].lower() + h[1:], h[:1].upper() + h[1:]):
        if c and c not in out:
            out.append(c)
    return out


def direct_titles(de):
    """Commons file names to try directly for phrases that have no Wiktionary page ("De-Guten Morgen.oga")."""
    h = re.sub(r"^(der|die|das)\s+", "", de.strip())
    forms = []
    for f in (h, h.rstrip("?!.").strip()):
        for g in (f, f[:1].lower() + f[1:], f[:1].upper() + f[1:]):
            for x in (g, g.replace("'", "’")):
                if x not in forms:
                    forms.append(x)
    return ["File:De-%s.%s" % (f, ext) for f in forms for ext in ("ogg", "oga")]


def norm(s):
    return unicodedata.normalize("NFC", s.replace("_", " ")).casefold()


def match_rank(file_title, word):
    """0/1 = 'De-<word>.ogg' / 'De-<word>2.ogg', 2 = Lingua Libre recording of <word>, None = other word."""
    name = re.sub(r"^(Datei|File):", "", file_title)
    if not re.search(AUDIO_EXT, name, re.I):
        return None
    stem = re.sub(AUDIO_EXT, "", name, flags=re.I)
    m = re.match(r"^De-(.+?)(\d*)$", stem)
    if m and norm(m.group(1)) == norm(word):
        return 0 if not m.group(2) else 1
    m = re.match(r"^LL-Q188 \(deu\)-.+?-(.+)$", stem)
    if m and norm(m.group(1)) == norm(word):
        return 2
    return None


def find_recordings(titles):
    """title -> best matching Commons file title, for every title that has one."""
    found = {}
    titles = sorted(set(titles))
    for i in range(0, len(titles), 50):
        r = api(WIKT_API, {"action": "query", "prop": "images", "imlimit": "max", "titles": "|".join(titles[i:i + 50])})
        for p in r["query"]["pages"]:
            ranked = []
            for im in p.get("images", []):
                rank = match_rank(im["title"], p["title"])
                if rank is not None:
                    ranked.append((rank, im["title"]))
            if ranked:
                found[p["title"]] = "File:" + re.sub(r"^(Datei|File):", "", min(ranked)[1])
    return found


def file_info(file_titles):
    """Commons file title -> {mp3, artist, license, license_url, page}."""
    info = {}
    file_titles = sorted(set(file_titles))
    for i in range(0, len(file_titles), 50):
        r = api(COMMONS_API, {
            "action": "query", "titles": "|".join(file_titles[i:i + 50]),
            "prop": "imageinfo|videoinfo", "iiprop": "url|extmetadata", "viprop": "derivatives",
        })
        for p in r["query"]["pages"]:
            if p.get("missing") or not p.get("imageinfo"):
                continue
            meta = p["imageinfo"][0].get("extmetadata", {})
            mp3 = next((d["src"] for d in (p.get("videoinfo") or [{}])[0].get("derivatives", [])
                        if d.get("type", "").startswith("audio/mpeg")), None)
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
            info[p["title"]] = {
                "mp3": mp3,
                "artist": html.unescape(artist) or "Unknown",
                "license": meta.get("LicenseShortName", {}).get("value", "see source"),
                "license_url": meta.get("LicenseUrl", {}).get("value", ""),
                "page": p["imageinfo"][0]["descriptionurl"],
            }
    return info


def slug(word):
    s = word.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "word"


def write_credits(rows):
    items = "\n".join(
        '<tr><td lang="de">%s</td><td>%s</td><td>%s</td><td><a href="%s">%s</a></td></tr>' % (
            html.escape(de), html.escape(c["artist"]),
            ('<a href="%s">%s</a>' % (html.escape(c["license_url"]), html.escape(c["license"]))
             if c["license_url"] else html.escape(c["license"])),
            html.escape(c["page"]), html.escape(c["file"].replace("File:", "")))
        for de, c in rows)
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audio Credits</title>
<style>
:root{ --bg:#fff; --text:#1d1d1f; --dim:#666; --border:#e3e3e3; --link:#2b6cb0; }
@media (prefers-color-scheme: dark){ :root{ --bg:#141416; --text:#ececec; --dim:#a0a0a0; --border:#2c2c30; --link:#7fb3ff; } }
body{ background:var(--bg); color:var(--text); font:14px/1.5 system-ui,sans-serif; margin:0 auto; padding:24px 16px; max-width:900px; }
h1{ font-size:22px; margin:0 0 8px; } p{ color:var(--dim); } a{ color:var(--link); }
.wrap{ overflow-x:auto; } table{ border-collapse:collapse; width:100%%; font-size:13px; }
th,td{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); vertical-align:top; }
td:last-child{ word-break:break-all; }
</style></head><body>
<h1>Audio credits</h1>
<p>The word pronunciations in this course are recordings by native speakers from
<a href="https://commons.wikimedia.org/">Wikimedia Commons</a>, via <a href="https://de.wiktionary.org/">German Wiktionary</a>.
Each is used under the license shown; follow the source link for full details. %d recordings.
<a href="index.html">&larr; Back to the course</a></p>
<div class="wrap"><table><thead><tr><th>Word</th><th>Speaker</th><th>License</th><th>Source</th></tr></thead>
<tbody>
%s
</tbody></table></div>
</body></html>
""" % (len(rows), items)
    with open(os.path.join(AUDIO_DIR, "credits.html"), "w", encoding="utf-8") as f:
        f.write(page)


def build():
    with open("course_data.json", "r", encoding="utf-8") as f:
        vocab = json.load(f)["vocabulary"]
    words = []
    for level in vocab.values():
        for cat in level["categories"]:
            for w in cat["words"]:
                if w["de"] not in words:
                    words.append(w["de"])

    cands = {de: candidates(de) for de in words}
    recordings = find_recordings(t for cs in cands.values() for t in cs)
    infos = file_info(recordings.values())

    def wiktionary_match(de):
        return next((recordings[c] for c in cands[de] if c in recordings and infos.get(recordings[c], {}).get("mp3")), None)

    # second pass: phrases often sit on Commons without a Wiktionary page linking them
    direct = {de: direct_titles(de) for de in words if not wiktionary_match(de)}
    infos.update(file_info(t for ts in direct.values() for t in ts))

    os.makedirs(AUDIO_DIR, exist_ok=True)
    manifest, credits, missing, used = {}, [], [], {}
    for de in words:
        title = wiktionary_match(de) or next((t for t in direct.get(de, []) if infos.get(t, {}).get("mp3")), None)
        if not title:
            missing.append(de)
            continue
        info = infos[title]
        # one mp3 per Commons file, shared by entries that map to the same recording
        if title not in used:
            name = slug(re.sub(r"^File:De-|^File:", "", re.sub(AUDIO_EXT, "", title, flags=re.I))) + ".mp3"
            while name in used.values():
                name = name[:-4] + "-2.mp3"
            used[title] = name
            path = os.path.join(AUDIO_DIR, name)
            if not os.path.exists(path):
                download(info["mp3"], path)
                print("fetched", name)
        manifest[de] = used[title]
        credits.append((de, dict(info, file=title)))

    with open(os.path.join(AUDIO_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    write_credits(credits)

    stale = set(os.listdir(AUDIO_DIR)) - set(used.values()) - {"manifest.json", "credits.html"}
    for name in sorted(stale):
        if name.endswith(".mp3"):
            os.remove(os.path.join(AUDIO_DIR, name))
            print("removed stale", name)

    print("native recordings: %d / %d words" % (len(manifest), len(words)))
    print("browser voice fallback (%d):" % len(missing), ", ".join(missing))
    size = sum(os.path.getsize(os.path.join(AUDIO_DIR, n)) for n in used.values())
    print("audio/ size MB:", round(size / 1024 / 1024, 2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    build()
