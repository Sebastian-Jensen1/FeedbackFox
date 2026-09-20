const { query } = require("../db/pool");

// Slår restauranten op på Googles place_id og opretter den kun hvis vi ikke har
// den i forvejen. Upsert frem for INSERT, fordi man henter anmeldelser for det
// samme sted igen og igen — og navn, adresse og Google-score kan have ændret sig
// siden sidst.
async function upsertByPlaceId({
  googlePlaceId,
  name,
  businessType,
  address,
  googleRating,
  googleRatingCount,
}) {
  const { rows } = await query(
    `INSERT INTO restaurants
       (google_place_id, name, business_type, address, google_rating, google_rating_count)
     VALUES ($1, $2, $3, $4, $5, $6)
     ON CONFLICT (google_place_id) DO UPDATE SET
       name                = EXCLUDED.name,
       address             = EXCLUDED.address,
       google_rating       = EXCLUDED.google_rating,
       google_rating_count = EXCLUDED.google_rating_count,
       -- COALESCE, ikke overskrivning: branchen skriver ejeren selv i feltet
       -- øverst i dashboardet, og Google sender den ikke med. Uden denne ville
       -- hvert "Hent anmeldelser" slette det ejeren har skrevet.
       business_type       = COALESCE(EXCLUDED.business_type, restaurants.business_type)
     RETURNING *`,
    [
      googlePlaceId,
      name,
      businessType || null,
      address || null,
      googleRating ?? null,
      googleRatingCount ?? null,
    ]
  );
  return rows[0];
}

// Nyeste først, så dashboardet kan åbne det sted man sidst arbejdede på.
async function listAll() {
  const { rows } = await query("SELECT * FROM restaurants ORDER BY updated_at DESC");
  return rows;
}

async function findById(id) {
  const { rows } = await query("SELECT * FROM restaurants WHERE id = $1", [id]);
  return rows[0] || null;
}

// Tonen huskes pr. restaurant, så ejeren ikke skal vælge den forfra hver gang.
async function updateDefaultTone(id, tone) {
  const { rows } = await query(
    "UPDATE restaurants SET default_tone = $2 WHERE id = $1 RETURNING *",
    [id, tone || null]
  );
  return rows[0] || null;
}

module.exports = { upsertByPlaceId, listAll, findById, updateDefaultTone };
