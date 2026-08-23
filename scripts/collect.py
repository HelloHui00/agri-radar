"""agri-radar collector.

Reads D:\\agri-radar\\config\\sources.json, fetches new items from each
source, and prints STABLE JSON Lines to stdout.

Each line: {"ok": bool, "source": str, "tags": [...], "items": [...]}
On failure: {"ok": false, "source": str, "error": str}

Proxy: Clash Verge at 127.0.0.1:7897; per-source "proxy": true routes
that source through it. Everything else goes direct.
"""
import json, os, sys, ssl, socket, urllib.request, urllib.error
import xml.etree.ElementTree as ET
import email.utils
import datetime as dt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(BASE, "config", "sources.json")


def load_server_cfg():
    cfg_path = os.path.join(BASE, "config", "server.json")
    if not os.path.exists(cfg_path):
        return {}
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def get_proxy():
    """Return proxy URL. Disabled on Linux (no local clash) unless explicitly enabled."""
    import platform
    if platform.system() == "Linux":
        cfg_proxy = load_server_cfg().get("proxy", {})
        if cfg_proxy.get("enabled") and cfg_proxy.get("http_proxy"):
            return cfg_proxy["http_proxy"]
        return None
    # Windows: 优先 config，然后 env
    cfg = load_server_cfg()
    p = cfg.get("proxy", {})
    if p.get("enabled") and (p.get("http_proxy") or p.get("https_proxy")):
        return p.get("https_proxy") or p.get("http_proxy")
    return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


PROXY = get_proxy()
TIMEOUT = 20
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) agri-radar/1.0"}

# ---------------------------------------------------------------- network

def opener(use_proxy):
    if use_proxy:
        proxy = get_proxy()
        if proxy:
            return urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener()

def fetch(url, use_proxy=False, accept=None):
    headers = dict(UA)
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with opener(use_proxy).open(req, timeout=TIMEOUT) as r:
        return r.read()

# ---------------------------------------------------------------- xml/rss

def parse_rss_or_atom(data, source_name, tags, base_weight):
    """Lenient parser for both RSS 2.0 and Atom."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # strip junk before first '<'
        if isinstance(data, bytes):
            idx = data.find(b"<")
            if idx > 0:
                root = ET.fromstring(data[idx:])
            else:
                raise
        else:
            raise

    items = []
    ns = {"a": "http://www.w3.org/2005/Atom"}

    # RSS <item>
    for it in root.iter("item"):
        t = it.findtext("title") or ""
        l = it.findtext("link") or ""
        d = (it.findtext("pubDate") or it.findtext(
            "{http://purl.org/dc/elements/1.1/}date") or "")
        s = (it.findtext("description") or
             it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or "")
        if t.strip() and l.strip():
            items.append({"title": t.strip(), "url": l.strip(),
                          "published": d.strip(), "summary": s.strip(),
                          "source": source_name, "tags": tags,
                          "base_weight": base_weight})
    if items:
        return items

    # Atom <entry>
    for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
        t = e.findtext("a:title", namespaces=ns) or ""
        l = ""
        for link in e.findall("a:link", ns):
            if link.get("rel", "alternate") == "alternate":
                l = link.get("href", "")
                if l:
                    break
        d = (e.findtext("a:published", namespaces=ns) or
             e.findtext("a:updated", namespaces=ns) or "")
        s = (e.findtext("a:summary", namespaces=ns) or
             e.findtext("a:content", namespaces=ns) or "")
        if t.strip() and l.strip():
            items.append({"title": t.strip(), "url": l.strip(),
                          "published": d.strip(), "summary": s.strip(),
                          "source": source_name, "tags": tags,
                          "base_weight": base_weight})
    return items

def to_iso(s):
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d.astimezone(dt.timezone.utc).isoformat()
    except Exception:
        return s

# ---------------------------------------------------------------- sources

def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def do_rss(src):
    data = fetch(src["url"], src.get("proxy", False))
    items = parse_rss_or_atom(data, src["name"], src.get("tags", []),
                              src.get("base_weight", 3))
    for it in items:
        it["published"] = to_iso(it["published"])
    out({"ok": True, "source": src["name"], "tags": src.get("tags", []),
         "items": items})

def do_google_news(src):
    all_items, errs = [], []
    for q in src["queries"]:
        try:
            uq = urllib.parse.quote(q)
            lang = src.get("lang", "zh-CN")
            gl = src.get("gl", "CN")
            ceid = src.get("ceid", "CN:zh-Hans")
            url = ("https://news.google.com/rss/search?q="
                   f"{uq}+when:1d&hl={lang}&gl={gl}&ceid={urllib.parse.quote(ceid)}")
            data = fetch(url, src.get("proxy", False))
            items = parse_rss_or_atom(data, src["name"],
                                      src.get("tags", []),
                                      src.get("base_weight", 3))
            for it in items:
                it["published"] = to_iso(it["published"])
                it["query"] = q
            all_items.extend(items)
        except Exception as e:
            errs.append(f"{q}: {e}")
    # dedupe by url within this source
    seen, uniq = set(), []
    for it in all_items:
        if it["url"] not in seen:
            seen.add(it["url"])
            uniq.append(it)
    if uniq:
        out({"ok": True, "source": src["name"], "tags": src.get("tags", []),
             "items": uniq, "partial_errors": errs or None})
    else:
        out({"ok": False, "source": src["name"],
             "error": "; ".join(errs) or "no items"})

def do_crossref(src):
    """Latest works per journal, filtered client-side for recency."""
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=2)).date().isoformat()
    all_items, errs = [], []
    for j in src["journals"]:
        try:
            url = (f"https://api.crossref.org/journals/{j['issn']}/works"
                   f"?filter=from-pub-date:{cutoff}&rows=8"
                   f"&select=DOI,title,published,abstract,author,URL")
            data = json.loads(fetch(url, src.get("proxy", False),
                                    accept="application/json"))
            for w in data.get("message", {}).get("items", []):
                title = (w.get("title") or [""])[0]
                if not title:
                    continue
                doi = w.get("DOI", "")
                all_items.append({
                    "title": title,
                    "url": w.get("URL") or f"https://doi.org/{doi}",
                    "published": w.get("published", {}).get("date-time", ""),
                    "summary": (w.get("abstract") or "")[:600],
                    "source": j["name"],
                    "tags": src.get("tags", []),
                    "base_weight": src.get("base_weight", 3),
                })
        except Exception as e:
            errs.append(f"{j['name']}: {e}")
    if all_items:
        out({"ok": True, "source": src["name"], "tags": src.get("tags", []),
             "items": all_items, "partial_errors": errs or None})
    else:
        out({"ok": False, "source": src["name"],
             "error": "; ".join(errs) or "no items"})

def do_arxiv_search(src):
    """Search arXiv API for recent papers matching queries."""
    import urllib.parse
    all_items, errs = [], []
    for q in src["queries"]:
        try:
            # 整个 query 字符串都要 URL-encode，不能只 encode 里面的小段
            uq = urllib.parse.quote_plus(q)
            url = (f"https://export.arxiv.org/api/query?search_query={uq}"
                   f"&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending")
            data = fetch(url, src.get("proxy", False))
            items = parse_rss_or_atom(data, src["name"], src.get("tags", []),
                                      src.get("base_weight", 3))
            for it in items:
                it["published"] = to_iso(it["published"])
                it["query"] = q
            all_items.extend(items)
        except Exception as e:
            errs.append(f"{q}: {e}")
    # dedupe by url
    seen, uniq = set(), []
    for it in all_items:
        if it["url"] not in seen:
            seen.add(it["url"])
            uniq.append(it)
    if uniq:
        out({"ok": True, "source": src["name"], "tags": src.get("tags", []),
             "items": uniq, "partial_errors": errs or None})
    else:
        out({"ok": False, "source": src["name"],
             "error": "; ".join(errs) or "no items"})


# ---------------------------------------------------------------- main

HANDLERS = {"rss": do_rss, "google_news": do_google_news,
            "arxiv_search": do_arxiv_search, "rss_category": do_crossref}

def main():
    with open(SOURCES_PATH, encoding="utf-8") as f:
        sources = json.load(f)
    for src in sources:
        if not src.get("enabled", True):
            continue
        handler = HANDLERS.get(src["type"])
        if not handler:
            out({"ok": False, "source": src.get("name", "?"),
                 "error": f"unknown type {src['type']}"})
            continue
        try:
            handler(src)
        except Exception as e:
            out({"ok": False, "source": src.get("name", "?"),
                 "error": str(e)})

if __name__ == "__main__":
    socket.setdefaulttimeout(TIMEOUT)
    main()
