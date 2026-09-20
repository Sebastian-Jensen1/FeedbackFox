const { query, withTransaction } = require("../db/pool");

// Frontenden kender tre tilstande, databasen to. Forskellen er med vilje:
// "ready" er ikke en egenskab ved anmeldelsen, men ved om der findes et udkast
// til den — derfor udledes den her frem for at ligge i en kolonne der kan komme
// i modstrid med replies-tabellen.
function toClientStatus(row) {
  if (row.status === "answered") return "sent";
  if (row.draft_text) return "ready";
  return "new";
}

// Databaserækker bruger snake_case og har kolonner frontenden er ligeglad med.
// Alt der sendes til browseren går gennem denne, så formen er ens overalt.
function toClientReview(row) {
  return {
    id: row.id,
    externalId: row.external_id,
    reviewerName: row.reviewer_name || "",
    rating: row.rating,
    reviewText: row.review_text || "",
    publishedAt: row.published_at,
    status: toClientStatus(row),
    // Det ejeren sidst sendte vinder over udkastet — ellers ville en besvaret
    // anmeldelse vise modellens forslag frem for den tekst der faktisk blev brugt.
    draft: row.final_text || row.draft_text || "",
  };
}

// Gemmer en hel hentning fra Google på én gang, i én transaktion: enten lander
// alle fem anmeldelser, eller ingen. En halv hentning er værre end ingen, fordi
// man ikke kan se på listen at der mangler noget.
async function upsertMany(restaurantId, reviews) {
  if (reviews.length === 0) return [];

  return withTransaction(async (client) => {
    const saved = [];
    for (const review of reviews) {
      const { rows } = await client.query(
        `INSERT INTO reviews
           (restaurant_id, external_id, reviewer_name, rating, review_text, published_at)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (restaurant_id, external_id) DO UPDATE SET
           reviewer_name = EXCLUDED.reviewer_name,
           rating        = EXCLUDED.rating,
           review_text   = EXCLUDED.review_text,
           published_at  = EXCLUDED.published_at
           -- status og answered_at røres bevidst IKKE. Google sender de samme
           -- anmeldelser hver gang, så uden denne udeladelse ville et tryk på
           -- "Hent anmeldelser" sætte alt besvaret arbejde tilbage til "ny".
         RETURNING *`,
        [
          restaurantId,
          review.externalId,
          review.reviewerName || null,
          review.rating ?? null,
          review.reviewText || null,
          review.publishTime || null,
        ]
      );
      saved.push(rows[0]);
    }
    return saved;
  });
}

// Henter anmeldelser med det nyeste udkast hæftet på. LATERAL frem for et kald
// pr. anmeldelse: ellers bliver det én forespørgsel per række, og over en
// forbindelse til skyen koster hver af dem rigtig ventetid.
async function listByRestaurant(restaurantId) {
  const { rows } = await query(
    `SELECT rv.*, rp.draft_text, rp.final_text
       FROM reviews rv
       LEFT JOIN LATERAL (
         SELECT draft_text, final_text
           FROM replies
          WHERE review_id = rv.id
          ORDER BY created_at DESC
          LIMIT 1
       ) rp ON true
      WHERE rv.restaurant_id = $1
      ORDER BY rv.published_at DESC NULLS LAST, rv.created_at DESC`,
    [restaurantId]
  );
  return rows;
}

async function findById(id) {
  const { rows } = await query("SELECT * FROM reviews WHERE id = $1", [id]);
  return rows[0] || null;
}

// Bruges af "Markér som besvaret", når ejeren allerede har svaret ude på Google
// og der derfor ikke er noget udkast at gemme.
async function markAnswered(id) {
  const { rows } = await query(
    `UPDATE reviews SET status = 'answered', answered_at = now()
      WHERE id = $1 RETURNING *`,
    [id]
  );
  return rows[0] || null;
}

module.exports = {
  upsertMany,
  listByRestaurant,
  findById,
  markAnswered,
  toClientReview,
};
