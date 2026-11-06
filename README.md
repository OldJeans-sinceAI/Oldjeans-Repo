# Näkyvyystesti (Windows)

Fonectan näkyvyystestin kaltainen paikallinen työkalu. Se tarkistaa, löytyykö yritys yhdeksästä kanavasta (Google Maps, Fonecta, Facebook, LinkedIn, Finder, Kauppalehti, Asiakastieto, Instagram, arvostelusivustot), ja arvioi yrityksen oman verkkosivuston tekniset perusasiat. Lopuksi se antaa pisteet (0-100), tärkeysjärjestetyn korjauslistan sekä ladattavan HTML- ja JSON-raportin.

## Asennus ja käynnistys

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Jos aktivointi estyy, ohita kaksi ensimmäistä riviä ja aja asennus ja käynnistys suoraan `py -m`-komennoilla.

## Pisteytys

- Kanavat 60 %: Google 20, Fonecta 15, Facebook 12, LinkedIn 10, Finder 8, Kauppalehti 8, Asiakastieto 7, Instagram 5, arvostelusivustot 5. Täysi osuma antaa koko painon, epävarma osuma 40 %.
- Verkkosivusto 40 %: HTTPS ja aukeaminen 20, Schema.org 15, title, description, H1, viewport, puhelin ja paikkakunta 10 kutakin, robots.txt 5.

## Rajoitukset

- Löytyminen perustuu DDGS-hakuun, ei kanavien omiin rajapintoihin. Se voi jättää profiileja löytämättä, ja haku voi rajoittaa pyyntöjä. Tuotantoon tarvitaan virallinen hakupalvelun API ja esim. Google Places API.
- Pisteet ovat tämän työkalun oma mittari, eivät Google-sijoitus tai Fonectan menetelmä.
- Sivuston haku estää sisäverkko-osoitteet (SSRF) ja lukee enintään 1,5 Mt sivua kohti.
- Noudata hakupalvelujen ja sivustojen käyttöehtoja, robots.txt-ohjeita ja tietosuojalainsäädäntöä.
