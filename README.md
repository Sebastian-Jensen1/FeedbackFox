# Review Assistant — dashboard-prototype

Et dashboard hvor en butiksejer kan hente virksomhedens anmeldelser fra Google,
vælge hvilke der skal have AI-genereret svar (fx alle 5-stjernede),
gennemgå/redigere udkastet, og trykke "Send". Dette er en **MVP til at teste
konceptet og flowet** — "Send til Google" kopierer til udklipsholder i stedet
for at poste direkte (se afsnittet om Google Business Profile API nedenfor).

Backenden er skrevet i Python med [FastAPI](https://fastapi.tiangolo.com/), og data
gemmes i PostgreSQL på Neon. Frontenden er én HTML-fil (`public/index.html`), som
backenden selv serverer.

## Sådan kører du den i VS Code

Du skal bruge [uv](https://docs.astral.sh/uv/) (Python-pakkehåndtering; på Mac:
`brew install uv`). Python 3.14 hentes af uv, hvis du ikke har den.

1. Åbn mappen `review-assistant` i VS Code (`File > Open Folder`)
2. Åbn integreret terminal (`Ctrl+\`` / `Cmd+\``) og gå ind i backend-mappen:
   ```
   cd python-backend
   ```
3. Installer afhængigheder:
   ```
   uv sync
   ```
4. Kopiér `.env.example` til `.env`:
   ```
   cp .env.example .env
   ```
5. Åbn `.env` og indsæt din egen Anthropic API-nøgle (hent en gratis på https://console.anthropic.com/settings/keys — kræver et lille indestående på kontoen, typisk et par kroner er nok til at teste)
6. Sæt databasen op (se afsnittet nedenfor)
7. Start serveren:
   ```
   uv run python -m app
   ```
8. Åbn http://localhost:3000 i browseren

Serveren lytter kun på din egen maskine (`127.0.0.1`), så den kan ikke nås fra andre
computere. Det er med vilje, se "Sikkerhed" nedenfor.

## Database (PostgreSQL på Neon)

Databasen ligger hos [Neon](https://neon.tech/) og kører døgnet rundt, så vi
begge arbejder mod de samme data uden at nogens computer skal være tændt.

### Hvis databasen allerede er sat op (det normale)

1. Få forbindelsesstrengen af den anden — den står **ikke** i Git, fordi den
   indeholder adgangskoden til databasen
2. Sæt den ind som `DATABASE_URL` i `python-backend/.env` (uden mellemrum omkring `=`)
3. `uv run python -m app.db.migrate` — opretter de tabeller du eventuelt mangler
4. `uv run python -m app`

### Første gang databasen oprettes

1. Opret en gratis konto på https://neon.tech (ingen betalingskort)
2. Opret et projekt — vælg region **EU (Frankfurt)**, så data bliver i EU og
   svartiden fra Danmark er lav
3. Kopiér "Connection string" fra dashboardet. Den ser sådan ud:
   ```
   postgresql://bruger:adgangskode@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Sæt den ind i `python-backend/.env` som `DATABASE_URL`, men ret `sslmode=require`
   til `sslmode=verify-full` — se `.env.example` for hvorfor
5. Kør `uv run python -m app.db.migrate`

Databasen hedder `neondb`. Det er med vilje: det er den Neon selv opretter, og
vores tabeller ligger inde i den. Der skal ikke oprettes en `feedbackfox`.

Neons onboarding foreslår også `neon skills`, `neon mcp`, `neon config init` og
`neon deploy`. Det er deres infrastructure-as-code-værktøj og agent-integrationer —
vi bruger ingen af delene. Projektet snakker helt almindelig Postgres via
`psycopg`, så der skal kun bruges en forbindelsesstreng.

### Fælles database — hvad det betyder i praksis

- I ser **de samme anmeldelser og svar med det samme**. Sletter den ene noget,
  er det også væk for den anden
- Skal I teste noget rodet, så skift midlertidigt til en lokal database (se
  `.env.example`) — eller lav en gratis **branch** i Neon, som er en kopi af
  data I kan arbejde i uden at ødelægge noget
- Neon lukker databasen ned når den ikke bruges, og starter den igen ved næste
  forespørgsel. Første kald efter en pause tager derfor et øjeblik. Det er ikke
  en fejl, og ventetiden i `app/db/pool.py` er sat høj nok til det

### Del aldrig forbindelsesstrengen i Git

`DATABASE_URL` indeholder adgangskoden til hele databasen. `.env` er i
`.gitignore` og skal blive der. Send strengen til hinanden på en måde der ikke
ligger offentligt — og hvis den først er havnet i en commit, så skift
adgangskoden i Neon med det samme frem for bare at slette linjen.

`app/db/pool.py` kræver desuden et gyldigt certifikat for alt der ikke er
localhost. Det er bevidst ikke overladt til `sslmode` i forbindelsesstrengen: en
streng med `sslmode=disable` ville ellers slå tjekket fra, uden at man kunne se det
nogen steder i koden. Får du en certifikatfejl, så sig til frem for at slå
verifikationen fra — så er der noget galt der er værd at kigge på.

### Migrationer

```
uv run python -m app.db.migrate
```

Kommandoen er idempotent: den holder styr på hvad der er kørt i tabellen
`schema_migrations` og springer det over næste gang.

Skemaændringer laves som en **ny** fil i `python-backend/app/db/migrations/` (fx
`002_tilføj_kolonne.sql`). Ret aldrig i en migration der allerede er kørt — den
er kørt på den fælles database, og en rettelse i filen bliver aldrig udført der.

### Kigge direkte i dataene

Nemmest er "SQL Editor" i Neons dashboard. Vil du hellere bruge terminalen, kan
du bruge `psql` fra Postgres.app med den samme forbindelsesstreng:

```
/Applications/Postgres.app/Contents/Versions/latest/bin/psql "DIN_DATABASE_URL"
```

Er du træt af den lange sti, så læg den i `PATH` én gang:

```
sudo mkdir -p /etc/paths.d && echo /Applications/Postgres.app/Contents/Versions/latest/bin | sudo tee /etc/paths.d/postgresapp
```

Nyttige kommandoer: `\dt` (vis tabeller), `\d reviews` (vis kolonner),
`SELECT * FROM reviews;`, `\q` (afslut).

## Hvordan du bruger den

1. Indtast virksomhedsnavn og branche øverst
2. Søg din virksomhed op i boksen (tryk Enter eller "Søg på Google"), vælg den rigtige i resultatlisten, og klik "Hent seneste anmeldelser" — de lander under "Nye / ubesvarede"
3. Brug filter-chips (fx "★★★★★") til at vælge en gruppe, sæt flueben ved dem du vil have svar til
4. Klik "Generér svar for valgte" — udkast dukker op under hver anmeldelse, redigérbare
5. Klik "Send til Google" — kopierer svaret til udklipsholderen og flytter anmeldelsen til "Besvarede"-fanen
6. Har en anmeldelse allerede fået svar direkte på Google (fx før I brugte dette værktøj), sæt flueben ved den og klik "Markér som besvaret" for at flytte den til "Besvarede" uden at generere et nyt svar

## Tests

Kør dem fra `python-backend/`:

```
uv run pytest
```

Der er to slags tests. Ingen af dem koster penge eller rører jeres rigtige data:

- **Uden database** (`tests/test_unit.py`): validering, sikkerhedsheaders, prompten,
  TLS-opsætningen og fejlhåndtering.
- **Med database** (`tests/test_api_db.py`): hele flowet fra Google-hentning til
  "Send". De kører i et midlertidigt schema med tilfældigt navn i Neon, som oprettes
  før og slettes efter. Google og Claude er falske. Mangler `DATABASE_URL`, springes
  de over.

## Sikkerhed

- **Al input valideres** med typer og grænser (fx højst 25 anmeldelser pr. kald,
  svar højst 4096 tegn, id'er skal være UUID'er). Fejl svarer med de feltnavne der er
  galt, aldrig med det klienten sendte.
- **Kun parametriseret SQL.** Ingen værdier bygges ind i SQL-tekst.
- **Anmeldelsernes tekst læses fra databasen**, ikke fra det browseren sender med
  til `/api/generate`, og den står i tags i prompten, som Claude får besked på at
  behandle som data (beskytter mod "prompt injection" fra anmeldere).
- **Fejl fra Google, Claude og databasen sendes ikke videre til browseren.** De
  logges på serveren; brugeren får en tekst vi selv har skrevet.
- **Anmeldelser vises som ren tekst.** Frontenden renser alt fra Google og Claude,
  før det sættes ind i siden, så en anmeldelse ikke kan køre kode i browseren
  ("XSS"). Som ekstra lag tillader en CSP kun det indlejrede script i `index.html`
  (udpeget ved dets hash), siden kan ikke lægges i en iframe, og API-svar caches ikke.
- **`Host`-tjek** (`ALLOWED_HOSTS`) mod DNS rebinding, og serveren binder kun til
  `127.0.0.1`.
- **Grænse for request-størrelse** (256 KB), timeouts på alle eksterne kald, og
  `/docs` er slukket som standard (tænd med `ENABLE_DOCS=1`).
- **Ingen redirects** følges ved kald til Google, så API-nøglen aldrig sendes videre.

**Kendt begrænsning:** der er intet login. Alle der kan nå serveren kan bruge dine
API-nøgler og læse og ændre dataene. Derfor lytter den kun på din egen maskine. Skal
den ud på internettet, skal der login foran først (står også under "Hvad der ellers
mangler").

## Vejen til "1-knap send direkte til Google"

Lige nu er "Send"-knappen en placeholder (kopiér til udklipsholder). For at den
reelt poster svaret på Google, skal I igennem **Google Business Profile API**:

1. Ansøg om adgang via Google Cloud Console — kræver en verificeret Google
   Business-profil der har været aktiv i 60+ dage, samt en beskrivelse af jeres
   brug. Godkendelsen tager tid, så søg tidligt.
2. Hver restaurant-kunde skal selv logge ind med sin egen Google-konto via
   OAuth 2.0 og godkende adgang — det er ikke noget du kan gøre på deres vegne
   uden deres aktive login.
3. Når adgangen er givet, bruges `accounts.locations.reviews.updateReply`
   endpointet til selve afsendelsen.

Indtil da er kopiér-til-udklipsholder en helt fin (og etisk sikker) måde at
demonstrere værdien for kunderne på.

## Automatisk hentning af anmeldelser (Google Places API)

I boksen øverst kan du søge din virksomhed op på Google og hente dens seneste
anmeldelser automatisk.

For at det virker:

1. Indsæt en `GOOGLE_PLACES_API_KEY` i `python-backend/.env` (se `.env.example`)
2. I [Google Cloud Console](https://console.cloud.google.com/apis/library): aktivér
   **"Places API (New)"** for det projekt nøglen tilhører
3. Sørg for at projektet har en **billing-konto** koblet på — Places API kræver
   det, selvom I ikke overskrider den gratis månedlige kvote
4. Hvis nøglen har API-restriktioner sat (Credentials → din nøgle → "API restrictions"),
   skal "Places API (New)" stå på listen over tilladte API'er

**Vigtig begrænsning:** Google udstiller kun de **5 mest relevante anmeldelser**
pr. sted via denne API — ikke jeres fulde historik. Det er en begrænsning i
Google's API, ikke noget der kan konfigureres væk. Til at hente og besvare
*alle* anmeldelser (og poste svar direkte) kræves Google Business Profile API,
se afsnittet ovenfor.

## Hvad der ellers mangler før det er et rigtigt produkt

- **Login**: som nævnt under "Sikkerhed" er der intet login endnu, og serveren må derfor kun køre lokalt.
- **"Nye siden sidst"-tælleren** tæller nu de anmeldelser der reelt står som ubesvarede i databasen. Den mangler stadig at tage højde for *hvornår ejeren sidst var inde* — så "ny" betyder "ikke besvaret endnu", ikke "kommet til siden dit sidste besøg".
- **Flere virksomheder pr. kunde**: hvis I vil have flere kunder, skal hver have sit eget "workspace" med egen liste af anmeldelser.
- **Betaling**: Stripe-integration til abonnement, hvis I vil automatisere fakturering.

## Filstruktur

```
review-assistant/
├── public/index.html            # Frontend (form + resultater), serveres af backenden
└── python-backend/
    ├── pyproject.toml           # Afhængigheder (uv.lock låser præcise versioner)
    ├── .env.example             # Skabelon — kopiér til .env
    ├── .env                     # DINE nøgler (opret selv, committes aldrig)
    ├── app/
    │   ├── main.py              # Selve appen: samler routes, sikkerhed og opstart
    │   ├── __main__.py          # Startknap: uv run python -m app
    │   ├── routers/             # HTTP-endpoints (det browseren kalder)
    │   ├── schemas/             # Tjekker og former data ind og ud
    │   ├── services/            # Claude- og Google Places-kald
    │   ├── models/              # Al SQL, én fil pr. tabel
    │   ├── db/
    │   │   ├── pool.py          # Forbindelsen til databasen
    │   │   ├── migrate.py       # Migrations-runner
    │   │   └── migrations/      # Nummererede .sql-filer, køres i rækkefølge
    │   └── core/                # Indstillinger, fejlhåndtering og sikkerhed
    └── tests/                   # uv run pytest
```

**Vigtigt:** `.env` ligger allerede i `.gitignore` og skal blive der — den
indeholder både API-nøgler og adgangskoden til databasen.

## API-endpoints

| Metode | Sti | Hvad den gør |
| --- | --- | --- |
| `GET` | `/api/places/search?query=` | Søger et sted op hos Google. Rører ikke databasen. |
| `GET` | `/api/places/reviews?placeId=` | Henter fra Google, **gemmer** stedet og anmeldelserne, og svarer med det der nu står i databasen. |
| `GET` | `/api/restaurants` | Alle gemte steder, senest brugte først. Kaldes når siden åbnes. |
| `GET` | `/api/restaurants/{id}/reviews` | Alle anmeldelser for et sted, med nyeste udkast hæftet på. |
| `POST` | `/api/generate` | Genererer udkast med Claude og gemmer hvert af dem i `replies`. |
| `POST` | `/api/reviews/{id}/send` | Gemmer den tekst der faktisk blev sendt, og markerer anmeldelsen besvaret. |
| `POST` | `/api/reviews/{id}/answered` | Markerer besvaret uden at gemme en tekst (svaret blev givet på Google). |
