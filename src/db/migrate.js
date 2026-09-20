const fs = require("fs");
const path = require("path");
const { pool, query, withTransaction } = require("./pool");

const MIGRATIONS_DIR = path.join(__dirname, "migrations");

// Migrationer køres i filnavn-rækkefølge, derfor nummer-præfikset (001_, 002_, ...).
// Sorteringen er alfabetisk, så præfikset skal have samme antal cifre hele vejen.
function migrationFiles() {
  if (!fs.existsSync(MIGRATIONS_DIR)) return [];
  return fs
    .readdirSync(MIGRATIONS_DIR)
    .filter((file) => file.endsWith(".sql"))
    .sort();
}

// Uden denne tabel ville vi ikke kunne kende forskel på "migration er kørt" og
// "migration er ny", og hver kørsel ville forsøge at oprette tabellerne igen.
async function ensureMigrationsTable() {
  await query(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      filename   TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
  `);
}

async function appliedMigrations() {
  const { rows } = await query("SELECT filename FROM schema_migrations");
  return new Set(rows.map((row) => row.filename));
}

async function migrate() {
  await ensureMigrationsTable();

  const applied = await appliedMigrations();
  const pending = migrationFiles().filter((file) => !applied.has(file));

  if (pending.length === 0) {
    console.log("Databasen er allerede opdateret — ingen nye migrationer.");
    return;
  }

  for (const file of pending) {
    const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, file), "utf8");

    // Både SQL'en og registreringen af den ligger i samme transaktion. Fejler
    // migrationen halvvejs, rulles alt tilbage, og filen tælles ikke som kørt —
    // ellers stod databasen i en tilstand som ingen migration beskriver.
    await withTransaction(async (client) => {
      await client.query(sql);
      await client.query("INSERT INTO schema_migrations (filename) VALUES ($1)", [file]);
    });

    console.log(`Kørte migration: ${file}`);
  }

  console.log(`Færdig — ${pending.length} migration(er) kørt.`);
}

// Kørt direkte fra kommandolinjen (npm run migrate) frem for importeret af appen:
// skemaændringer skal være et bevidst valg, ikke noget der sker ved serverstart.
if (require.main === module) {
  migrate()
    .then(() => pool.end())
    .catch(async (err) => {
      console.error("Migration fejlede:", err.message);
      await pool.end();
      process.exit(1);
    });
}

module.exports = { migrate };
