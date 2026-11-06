# Näkyvyystesti (Windows)

Fonectan näkyvyystestin kaltainen paikallinen työkalu. Se tarkistaa, löytyykö yritys yhdeksästä kanavasta (Google Maps, Fonecta, Facebook, LinkedIn, Finder, Kauppalehti, Asiakastieto, Instagram, arvostelusivustot), ja arvioi yrityksen oman verkkosivuston tekniset perusasiat. Lopuksi se antaa pisteet (0-100), tärkeysjärjestetyn korjauslistan sekä ladattavan HTML- ja JSON-raportin.

## Asennus ja käynnistys

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1

```

Jos aktivointi estyy, ohita kaksi ensimmäistä riviä ja aja asennus ja käynnistys suoraan `py -m`-komennoilla.

## Node-versionhallinta (nvm)

Projekti käyttää Node-versiota, joka on lukittu tiedostoon `.nvmrc` (`20.11.0`). Sama versio on käytössä GitHub Actions -testissä, ja `package.json`:n `engines`-kenttä sekä `.npmrc`:n `engine-strict=true` estävät asennuksen väärällä versiolla.

Kertaluonteinen asennus (macOS / Linux / WSL):

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc   # tai ~/.zshrc
nvm --version      # tulee näyttää versionumeron
```

Windows (PowerShell): nvm ei toimi suoraan, asenna [nvm-windows](https://github.com/coreybutler/nvm-windows) ja aja `nvm install 20.11.0` sekä `nvm use 20.11.0` (nvm-windows ei lue `.nvmrc`-tiedostoa automaattisesti).

Projektin Node-version käyttöönotto (projektin juuressa):

```bash
nvm install    # asentaa .nvmrc:n version, jos puuttuu
nvm use        # vaihtaa siihen
node -v        # tulee näyttää v20.11.0
```

## Testit

1. Luo `.env` mallin pohjalta ja täytä omat avaimesi (`.env` on `.gitignore`:ssa, eikä sitä viedä GitHubiin):

```bash
cp env_mockup .env
```

2. Asenna riippuvuudet ja aja yhteystesti:

```bash
nvm use
npm ci
npm run test:yext
```

Testin onnistumiseen projektisi juuressa tulee olla `.env`-tiedosto oikeilla avaimilla. Onnistuessaan testi tulostaa `✅ Success!` ja yrityksen nimen. GitHubissa sama testi ajetaan automaattisesti `main`-haaraan pushatessa ja pull requestissa (`.github/workflows/backend-test.yml`), avaimet haetaan repositoryn secreteistä.

## Komento-opas

| Tarkoitus | Komento |
| --- | --- |
| Tarkista nvm | `nvm --version` |
| Asenna projektin Node-versio (.nvmrc) | `nvm install` |
| Ota projektin Node-versio käyttöön | `nvm use` |
| Näytä aktiivinen Node / npm | `node -v` / `npm -v` |
| Näytä asennetut Node-versiot | `nvm ls` |
| Aseta oletusversio uusiin terminaaleihin | `nvm alias default 20.11.0` |
| Asenna riippuvuudet lukitusta lockfilesta (suositus) | `npm ci` |
| Asenna riippuvuudet ja päivitä lockfile | `npm install` |
| Puhdas uudelleenasennus | `rm -rf node_modules && npm ci` |
| Aja Yext-yhteystesti | `npm run test:yext` |
| Luo `.env` mallista | `cp env_mockup .env` |

Vianetsintä:

- `nvm: command not found`: avaa terminaali uudelleen tai aja `source ~/.bashrc` (tai `~/.zshrc`).
- `EBADENGINE` / "Unsupported engine": aja `nvm use` ja yritä uudelleen.
- `Cannot find module 'dotenv'` tai `'axios'`: aja `npm ci`.
- `❌ Connection failed` ja tyhjät arvot: tarkista, että `.env` on projektin juuressa ja avaimet on täytetty.
- Versionvaihto: muuta numero `.nvmrc`-tiedostoon (ja tarvittaessa `engines`-kenttään `package.json`:ssa), aja `nvm install`, `nvm use` ja `npm ci`. Voit päivittää lockfilen vasta tämän jälkeen komennolla `npm install`.

## Pisteytys

- Kanavat 60 %: Google 20, Fonecta 15, Facebook 12, LinkedIn 10, Finder 8, Kauppalehti 8, Asiakastieto 7, Instagram 5, arvostelusivustot 5. Täysi osuma antaa koko painon, epävarma osuma 40 %.
- Verkkosivusto 40 %: HTTPS ja aukeaminen 20, Schema.org 15, title, description, H1, viewport, puhelin ja paikkakunta 10 kutakin, robots.txt 5.

## Rajoitukset

- Löytyminen perustuu DDGS-hakuun, ei kanavien omiin rajapintoihin. Se voi jättää profiileja löytämättä, ja 
