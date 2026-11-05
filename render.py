"""HTML/CSS-renderöinti tuloksille. Kaikki käyttäjän syöte ja verkosta haettu teksti escapataan."""
from html import escape as e

CSS = """
:root{--ink:#10222B;--paper:#F3F6F7;--card:#fff;--line:#D5DDE1;--mute:#5A6B73;--amber:#FFC20E;--ok:#1E7B55;--bad:#B3382C;--maybe:#B07A00}
.nt{color:var(--ink);font-family:"Segoe UI",system-ui,-apple-system,sans-serif;line-height:1.5}
.nt *{box-sizing:border-box}
.nt h2{font-size:1.15rem;margin:2rem 0 .6rem;font-weight:700}
.nt-hero{background:var(--ink);color:#fff;border-radius:6px;padding:1.6rem 1.8rem;display:grid;grid-template-columns:auto 1fr;gap:1.8rem;align-items:center}
.nt-score{font-size:4.2rem;font-weight:800;line-height:1;letter-spacing:-.03em}
.nt-score small{font-size:1.2rem;font-weight:500;opacity:.7;letter-spacing:0}
.nt-verdict{font-size:1.25rem;font-weight:700;margin:0 0 .2rem}
.nt-sub{opacity:.78;margin:0 0 .9rem;font-size:.95rem}
.nt-bar{display:flex;gap:3px;height:12px}
.nt-bar i{flex:1;border-radius:2px;background:#3A4F5A}
.nt-bar i.found{background:var(--amber)}.nt-bar i.maybe{background:#8A7A3A}
.nt-legend{font-size:.8rem;opacity:.7;margin-top:.4rem}
.nt-row{display:grid;grid-template-columns:13rem 7rem 1fr;gap:.8rem;padding:.7rem 0;border-top:1px solid var(--line);align-items:baseline}
.nt-row:first-child{border-top:0}
.nt-row.two{grid-template-columns:15rem 1fr}
.nt-box{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:.4rem 1.2rem}
.nt-name{font-weight:600}
.nt-pill{display:inline-block;padding:.1rem .55rem;border-radius:99px;font-size:.82rem;font-weight:600;border:1.5px solid}
.nt-pill.found,.nt-pill.ok{color:var(--ok);border-color:var(--ok)}
.nt-pill.missing,.nt-pill.no,.nt-pill.error{color:var(--bad);border-color:var(--bad)}
.nt-pill.maybe{color:var(--maybe);border-color:var(--maybe)}
.nt-det{color:var(--mute);font-size:.9rem;overflow-wrap:anywhere}
.nt-det a{color:var(--ink)}
.nt-rec{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--line);border-radius:6px;padding:.7rem 1rem;margin:.5rem 0}
.nt-rec.high{border-left-color:var(--bad)}.nt-rec.mid{border-left-color:var(--amber)}
.nt-rec b{display:block}.nt-rec span{color:var(--mute);font-size:.92rem}
.nt-rec em{font-style:normal;font-size:.8rem;color:var(--mute);float:right}
.nt-note{color:var(--mute);font-size:.85rem;margin-top:1.5rem}
@media(max-width:700px){.nt-hero{grid-template-columns:1fr}.nt-row,.nt-row.two{grid-template-columns:1fr;gap:.2rem}}
@media print{.nt-hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""
STATUS = {"found": "Löytyi", "maybe": "Epävarma", "missing": "Ei löytynyt", "error": "Haku epäonnistui"}
IMPACT = {"high": "Suuri vaikutus", "mid": "Keskisuuri vaikutus", "low": "Pieni vaikutus"}


def verdict(score):
    if score >= 75:
        return "Hyvä näkyvyys", "Perusasiat ovat kunnossa. Korjaa vielä alla olevat puutteet."
    if score >= 45:
        return "Kohtalainen näkyvyys", "Yritys löytyy osasta kanavia, mutta asiakkaita jää saavuttamatta."
    return "Heikko näkyvyys", "Yritystä on vaikea löytää. Aloita suosituslistan ylimmistä kohdista."


def hero(r):
    v, sub = verdict(r["score"])
    segs = "".join(f'<i class="{c["status"]}" title="{e(c["channel"])}"></i>' for c in r["channels"])
    return (f'<div class="nt-hero"><div class="nt-score">{r["score"]}<small>/100</small></div><div>'
            f'<p class="nt-verdict">{v}: {e(r["company"])}</p><p class="nt-sub">{sub}</p>'
            f'<div class="nt-bar">{segs}</div>'
            f'<div class="nt-legend">{r["found_channels"]} / {len(r["channels"])} kanavaa löytyi</div></div></div>')


def channels(r):
    rows = []
    for c in r["channels"]:
        link = f'<a href="{e(c["url"])}" target="_blank" rel="noopener noreferrer">{e(c["title"] or c["url"])[:90]}</a>' if c["url"] else e(c["error"] or "")
        rows.append(f'<div class="nt-row"><div class="nt-name">{e(c["channel"])}</div>'
                    f'<div><span class="nt-pill {c["status"]}">{STATUS[c["status"]]}</span></div>'
                    f'<div class="nt-det">{link}</div></div>')
    return '<h2>Missä yritys näkyy</h2><div class="nt-box">' + "".join(rows) + "</div>"


def website(r):
    s = r["site"]
    if not s:
        return '<h2>Verkkosivusto</h2><div class="nt-box"><div class="nt-row two"><div class="nt-name">Sivustoa ei löytynyt</div><div class="nt-det">Anna sivuston osoite lomakkeella ja aja testi uudelleen.</div></div></div>'
    rows = "".join(
        f'<div class="nt-row two"><div><span class="nt-pill {"ok" if c["ok"] else "no"}">{"OK" if c["ok"] else "Puutteellinen"}</span> '
        f'<span class="nt-name">{e(c["label"])}</span></div><div class="nt-det">{e(c["detail"])[:180]}</div></div>'
        for c in s["checks"])
    return (f'<h2>Verkkosivusto</h2><p class="nt-det">{e(s["url"])}</p><div class="nt-box">{rows}</div>')


def recs(r):
    if not r["recs"]:
        return '<h2>Suositukset</h2><p>Ei korjattavaa. Tulokset ovat kunnossa.</p>'
    items = "".join(f'<div class="nt-rec {x["impact"]}"><em>{IMPACT[x["impact"]]}</em><b>{e(x["title"])}</b><span>{e(x["text"])}</span></div>'
                    for x in r["recs"])
    return f'<h2>Mitä korjata ensin</h2>{items}'


NOTE = ('<p class="nt-note">Tulos perustuu julkiseen verkkohakuun ja sivuston HTML:n tekniseen tarkistukseen. '
        'Se ei mittaa Googlen sijoituksia eikä todellista markkinanäkyvyyttä. Hakukone voi jättää profiileja '
        'löytämättä, joten tarkista puuttuvat kanavat myös käsin.</p>')


def body(r):
    return f'<div class="nt">{hero(r)}{recs(r)}{channels(r)}{website(r)}{NOTE}</div>'


def report_html(r):
    return (f'<!doctype html><html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Näkyvyysraportti: {e(r["company"])}</title><style>body{{margin:0;padding:1.5rem;background:#F3F6F7;max-width:60rem;margin-inline:auto}}{CSS}</style></head>'
            f'<body>{body(r)}</body></html>')
