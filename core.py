"""Näkyvyystestin ydinlogiikka: kanavahaut, sivuston tarkistus, pisteytys. Ei Streamlit-riippuvuutta."""
import ipaddress
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NakyvyysTesti/2.0)"}
LEGAL = r"\b(oy|oyj|ab|ky|tmi|ay|osk|ry|ltd|inc)\b\.?"

# (nimi, verkkotunnus tai polku, paino, vinkki)
CHANNELS = [
    ("Google Maps / yrityskortti", ["google.com/maps", "maps.google", "g.page", "business.google"], 20,
     "Luo ja vahvista Google-yrityskortti. Se näkyy karttahauissa ja nimihauissa ensimmäisenä."),
    ("Fonecta", ["fonecta.fi"], 15, "Tarkista Fonectan yritysprofiili ja korjaa tiedot ajan tasalle."),
    ("Facebook", ["facebook.com"], 12, "Perusta yrityssivu ja lisää siihen osoite ja puhelinnumero."),
    ("LinkedIn", ["linkedin.com"], 10, "Luo LinkedIn-yrityssivu. Se tukee erityisesti B2B-näkyvyyttä."),
    ("Finder", ["finder.fi"], 8, "Lisää yritys Finderiin tai päivitä sen tiedot."),
    ("Kauppalehti", ["kauppalehti.fi"], 8, "Tarkista Kauppalehden yritystiedot ja yhteystiedot."),
    ("Asiakastieto", ["asiakastieto.fi"], 7, "Tarkista Asiakastiedon yritysprofiilin tiedot."),
    ("Instagram", ["instagram.com"], 5, "Instagram-tili auttaa etenkin kuluttajille suunnatuissa palveluissa."),
    ("Yelp / Tripadvisor", ["tripadvisor", "yelp."], 5, "Arvostelusivustot tukevat luottamusta, jos toimiala on kuluttajapalvelu."),
]
DIRECTORY_HOSTS = [d for _, doms, _, _ in CHANNELS for d in doms] + [
    "wikipedia.org", "youtube.com", "x.com", "twitter.com", "ytj.fi", "prh.fi", "yritystele.fi",
    "tiktok.com", "pinterest.", "duckduckgo.com", "bing.com", "google."]


# ---------- apufunktiot ----------
def norm_name(name):
    s = re.sub(LEGAL, " ", name.lower())
    s = re.sub(r"[^a-zåäö0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def digits_tail(phone):
    d = re.sub(r"\D", "", phone)
    if d.startswith("358"):
        d = d[3:]
    return d.lstrip("0")


def is_public_url(url):
    """Estä sisäverkkoon (SSRF) osoittavat osoitteet."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        for info in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def safe_get(url, timeout=10, max_bytes=1_500_000, hops=4):
    for _ in range(hops + 1):
        if not is_public_url(url):
            raise ValueError("Osoite ei ole julkinen verkko-osoite")
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=False, stream=True)
        if r.is_redirect and r.headers.get("location"):
            url = urljoin(url, r.headers["location"])
            r.close()
            continue
        raw = r.raw.read(max_bytes, decode_content=True)
        r.close()
        r.final_url = url
        r._content = raw
        r.encoding = r.encoding or r.apparent_encoding or "utf-8"
        return r
    raise ValueError("Liian monta uudelleenohjausta")


def search_web(query, limit=8):
    from ddgs import DDGS
    with DDGS() as d:
        return list(d.text(query, max_results=limit))


def host_of(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


# ---------- kanavat ----------
def check_channel(channel, company, city):
    name, domains, weight, tip = channel
    key = norm_name(company)
    best, url, title = 0.0, "", ""
    error = ""
    try:
        q = f"{company} {city} site:{domains[0].split('/')[0]}"
        if "google" in domains[0]:
            q = f"{company} {city} google maps"
        for it in search_web(q, 8):
            href = it.get("href") or it.get("url") or ""
            if not any(d in href.lower() for d in domains):
                continue
            blob = norm_name(" ".join([it.get("title", ""), it.get("body", ""), href]))
            score = 1.0 if key and key in blob else 0.4
            if score > best:
                best, url, title = score, href, it.get("title", "")
    except Exception as exc:
        error = str(exc)[:160]
    status = "found" if best >= 1 else "maybe" if best > 0 else ("error" if error else "missing")
    return {"channel": name, "status": status, "points": round(weight * best, 1), "weight": weight,
            "url": url, "title": title, "tip": tip, "error": error}


# ---------- verkkosivusto ----------
def find_website(company, city):
    key = norm_name(company).replace(" ", "")
    try:
        for it in search_web(f"{company} {city}", 10):
            href = it.get("href") or it.get("url") or ""
            h = host_of(href)
            if not h or any(d in href.lower() for d in DIRECTORY_HOSTS):
                continue
            if key and (key[:10] in h.replace("-", "") or key in norm_name(it.get("title", "")).replace(" ", "")):
                return f"{urlparse(href).scheme}://{urlparse(href).netloc}/"
    except Exception:
        pass
    return ""


def check_website(url, company, city, phone=""):
    checks = []

    def add(label, ok, pts, detail="", tip=""):
        checks.append({"label": label, "ok": bool(ok), "points": pts if ok else 0, "weight": pts,
                       "detail": detail, "tip": tip})

    try:
        r = safe_get(url)
    except Exception as exc:
        add("Sivusto aukeaa", False, 20, str(exc)[:160], "Varmista, että sivusto vastaa ja osoite on oikein.")
        return {"url": url, "checks": checks, "title": "", "description": "", "phones": [], "emails": [], "robots_note": ""}

    final = getattr(r, "final_url", url)
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    description = (desc_tag.get("content") or "").strip() if desc_tag else ""
    text = soup.get_text(" ", strip=True)
    phones = sorted(set(m.strip() for m in re.findall(r"(?:\+358|\b0)[\s-]?\d[\d\s-]{5,12}\d", text)))[:5]
    emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))[:5]

    add("Sivusto aukeaa ja käyttää HTTPS:ää", r.status_code < 400 and final.startswith("https"), 20,
        f"HTTP {r.status_code}", "Ota käyttöön HTTPS-varmenne ja ohjaa http-osoitteet https-osoitteisiin.")
    add("Sivun otsikko (title)", 10 <= len(title) <= 70, 10, title or "Puuttuu",
        "Kirjoita 10-70 merkin otsikko, jossa on yrityksen nimi ja paikkakunta.")
    add("Meta description", 50 <= len(description) <= 170, 10, description or "Puuttuu",
        "Lisää 50-170 merkin kuvaus, joka kertoo mitä yritys tekee ja missä.")
    add("H1-pääotsikko", soup.find("h1") is not None, 10, "", "Lisää etusivulle yksi selkeä H1-otsikko.")
    ld = soup.find_all("script", attrs={"type": "application/ld+json"})
    add("Rakenteinen data (Schema.org)", bool(ld), 15, f"{len(ld)} lohkoa" if ld else "",
        "Lisää LocalBusiness-merkintä, jossa on nimi, osoite ja puhelin. Se auttaa hakukoneita ja tekoälyhakuja.")
    add("Mobiiliskaalaus (viewport)", soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}) is not None, 10,
        "", "Lisää viewport-meta, jotta sivu toimii puhelimella.")

    if phone.strip():
        want = digits_tail(phone)
        ok = any(digits_tail(p) == want or want in digits_tail(p) for p in phones) or want in re.sub(r"\D", "", text)
        add("Puhelinnumero täsmää", ok, 10, ", ".join(phones) or "Numeroa ei löytynyt",
            "Näytä sama puhelinnumero sivustolla kuin muissa kanavissa.")
    else:
        add("Puhelinnumero näkyy", bool(phones), 10, ", ".join(phones) or "Ei löytynyt",
            "Näytä puhelinnumero selkeästi etusivulla tai yhteystiedoissa.")
    add("Paikkakunta mainitaan", bool(city.strip()) and city.lower() in text.lower(), 10, city,
        "Mainitse paikkakunta ja osoite sivuston tekstissä tai alatunnisteessa.")

    robots_note, robots_ok = "robots.txt puuttuu", False
    try:
        p = urlparse(final)
        rb = safe_get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=6, max_bytes=100_000)
        if rb.status_code == 200 and "user-agent" in rb.text.lower():
            blocked_all = re.search(r"user-agent:\s*\*\s*(?:#.*)?\n(?:\s*(?:allow|crawl-delay)[^\n]*\n)*\s*disallow:\s*/\s*$",
                                    rb.text, re.I | re.M)
            robots_ok = not blocked_all
            robots_note = "Estää kaikki robotit" if blocked_all else "Hakukoneet sallittu"
            bots = [b for b in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended") if b.lower() in rb.text.lower()]
            if bots:
                robots_note += f" · mainitsee: {', '.join(bots)}"
    except Exception:
        pass
    add("robots.txt sallii hakukoneet", robots_ok, 5, robots_note, "Tarkista, ettei robots.txt estä hakukoneita vahingossa.")
    return {"url": final, "checks": checks, "title": title, "description": description, "phones": phones, "emails": emails,
            "robots_note": robots_note}


# ---------- kokonaisuus ----------
def run_test(company, city, website="", phone="", progress=None):
    def tick(frac, msg):
        if progress:
            progress(frac, msg)

    tick(0.05, "Haetaan yrityksen tietoja eri kanavista...")
    with ThreadPoolExecutor(max_workers=3) as ex:
        channels = list(ex.map(lambda c: check_channel(c, company, city), CHANNELS))
    tick(0.7, "Etsitään verkkosivustoa...")
    site_url = website.strip()
    if site_url and not site_url.startswith("http"):
        site_url = "https://" + site_url
    if not site_url:
        site_url = find_website(company, city)
    site = None
    if site_url:
        tick(0.85, "Tarkistetaan verkkosivusto...")
        site = check_website(site_url, company, city, phone)

    ch_total = sum(c["weight"] for c in channels)
    ch_score = sum(c["points"] for c in channels) / ch_total
    site_score = (sum(c["points"] for c in site["checks"]) / sum(c["weight"] for c in site["checks"])) if site else 0.0
    score = round(100 * (0.6 * ch_score + 0.4 * site_score))

    recs = []
    for c in channels:
        if c["status"] in ("missing", "maybe"):
            recs.append({"impact": "high" if c["weight"] >= 12 else "mid",
                         "title": f"{c['channel']}: " + ("profiilia ei löytynyt" if c["status"] == "missing" else "osuma on epävarma"),
                         "text": c["tip"], "w": c["weight"]})
    if site:
        for c in site["checks"]:
            if not c["ok"]:
                recs.append({"impact": "high" if c["weight"] >= 15 else "mid" if c["weight"] >= 10 else "low",
                             "title": c["label"], "text": c["tip"], "w": c["weight"]})
    else:
        recs.append({"impact": "high", "title": "Verkkosivustoa ei löytynyt",
                     "text": "Anna sivuston osoite tai varmista, että yrityksellä on oma sivusto, joka löytyy nimellä.", "w": 30})
    recs.sort(key=lambda r: -r["w"])
    tick(1.0, "Valmis")
    return {"company": company, "city": city, "phone": phone, "score": score, "channels": channels,
            "site": site, "recs": recs,
            "found_channels": sum(c["status"] == "found" for c in channels)}
