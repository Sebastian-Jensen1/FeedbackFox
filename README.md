# Review Assistant — dashboard-prototype

Et dashboard hvor en butiksejer kan se nye anmeldelser, vælge hvilke der skal
have AI-genereret svar (fx alle 5-stjernede), gennemgå/redigere udkastet, og
trykke "Send". Dette er en **MVP til at teste konceptet og flowet** — anmeldelser
tilføjes stadig manuelt, og "Send til Google" kopierer til udklipsholder i
stedet for at poste direkte (se afsnittet om Google Business Profile API nedenfor).

## Sådan kører du den i VS Code

1. Åbn mappen `review-assistant` i VS Code (`File > Open Folder`)
2. Åbn integreret terminal (`Ctrl+\`` / `Cmd+\``)
3. Installer afhængigheder:
   ```
   npm install
   ```
4. Kopiér `.env.example` til `.env`:
   ```
   cp .env.example .env
   ```
5. Åbn `.env` og indsæt din egen Anthropic API-nøgle (hent en gratis på https://console.anthropic.com/settings/keys — kræver et lille indestående på kontoen, typisk et par kroner er nok til at teste)
6. Start serveren:
   ```
   npm start
   ```
7. Åbn http://localhost:3000 i browseren

## Hvordan du bruger den

1. Indtast virksomhedsnavn og branche øverst
2. Tilføj et par rigtige anmeldelser fra virksomhedens Google Maps-side i formularen nederst (kopiér navn, stjerner og tekst manuelt for nu — se afsnit om automatisk hentning nedenfor)
3. Brug filter-chips (fx "★★★★★") til at vælge en gruppe, sæt flueben ved dem du vil have svar til
4. Klik "Generér svar for valgte" — udkast dukker op under hver anmeldelse, redigérbare
5. Klik "Send til Google" — kopierer svaret til udklipsholderen og markerer anmeldelsen som besvaret

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

Under "Tilføj anmeldelse"-formularen kan du søge din virksomhed op på Google og
hente dens seneste anmeldelser automatisk i stedet for at copy-paste dem manuelt.

For at det virker:

1. Indsæt en `GOOGLE_PLACES_API_KEY` i `.env` (se `.env.example`)
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

- **"Nye siden sidst"-tælleren** er lige nu bare demo-data (status `"new"` sat i koden). I en rigtig version skal det beregnes ud fra hvornår ejeren sidst besøgte dashboardet, gemt i en database.
- **Login/flere virksomheder**: hvis I vil have flere kunder, skal hver have sit eget "workspace" med egen liste af anmeldelser.
- **Betaling**: Stripe-integration til abonnement, hvis I vil automatisere fakturering.

## Filstruktur

```
review-assistant/
├── server.js           # Express-backend, kalder Claude API
├── public/index.html   # Frontend (form + resultater)
├── package.json
├── .env.example         # Skabelon — kopiér til .env
└── .env                 # DIN nøgle (opret selv, committes aldrig)
```

**Vigtigt:** Læg `.env` i `.gitignore` hvis du opretter et Git-repo — den indeholder din API-nøgle.
