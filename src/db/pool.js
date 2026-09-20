const { Pool } = require("pg");
const { parse } = require("pg-connection-string");
const { DATABASE_URL } = require("../config/env");

if (!DATABASE_URL) {
  throw new Error(
    "DATABASE_URL mangler. Kopiér .env.example til .env og indsæt forbindelses-" +
      "strengen fra Neon (se afsnittet 'Database' i README)."
  );
}

// Strengen pilles fra hinanden her frem for at blive givet videre som
// connectionString. Det er ikke pyntearbejde: giver man begge dele til Pool,
// overskriver det som strengen siger om TLS det vi selv beder om — og så er
// vores ssl-indstilling nedenfor ren pynt uden virkning.
const parsed = parse(DATABASE_URL);

// TLS afgøres af HVEM vi taler med, ikke af hvad der tilfældigvis står i
// strengen. En streng med sslmode=no-verify (som Neons fejlfindingsvejledninger
// foreslår) ville ellers slå certifikat-tjekket fra uden at nogen opdagede det.
const LOCAL_HOSTS = ["localhost", "127.0.0.1", "::1"];
const isLocal = LOCAL_HOSTS.includes(parsed.host || "localhost");

// Certifikatet VERIFICERES for alt der ikke er localhost. Uden verifikation er
// forbindelsen krypteret, men vi har ingen garanti for at det er vores database
// i den anden ende — og både adgangskoden og alle anmeldelser går over
// internettet. Neon bruger almindelige Let's Encrypt-certifikater, som Node
// kender i forvejen, så der skal ikke konfigureres noget.
const ssl = isLocal ? false : { rejectUnauthorized: true };

// Én delt connection pool for hele appen. pg genbruger forbindelser, så vi ikke
// åbner en ny TCP-forbindelse til Postgres for hvert HTTP-kald.
const pool = new Pool({
  ...parsed,
  ssl,
  // En database i skyen kan være et sekund om at vågne (Neon lukker ned når den
  // ikke bruges). Standarden på 0 ms giver opgivelse før den når at svare.
  connectionTimeoutMillis: 10000,
});

// En tom pool logger ikke fejl af sig selv. Uden denne ville en database der falder
// ned, vælte hele Node-processen med en uncaught exception.
pool.on("error", (err) => {
  console.error("Uventet fejl på inaktiv database-forbindelse:", err.message);
});

// Alle forespørgsler går gennem denne, så vi har ét sted at logge eller måle dem.
function query(text, params) {
  return pool.query(text, params);
}

// Kører flere forespørgsler i én transaktion: enten gennemføres alle, eller ingen.
async function withTransaction(callback) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await callback(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    // Skal altid ske — ellers lækker forbindelsen og poolen løber tør.
    client.release();
  }
}

module.exports = { pool, query, withTransaction };
