const { query, withTransaction } = require("../db/pool");

// Hvert udkast bliver en ny række frem for en opdatering af den forrige. Trykker
// ejeren "Generér igen", er det netop interessant at kunne se begge forsøg —
// og historikken er det eneste grundlag vi har for at forbedre prompten senere.
async function insertDraft({ reviewId, draftText, tone, model }) {
  const { rows } = await query(
    `INSERT INTO replies (review_id, draft_text, tone, model)
     VALUES ($1, $2, $3, $4)
     RETURNING *`,
    [reviewId, draftText, tone || null, model || null]
  );
  return rows[0];
}

// Kaldes når ejeren trykker "Send til Google". Gemmer den tekst der faktisk blev
// sendt (som kan være redigeret) og markerer anmeldelsen som besvaret.
async function markSent(reviewId, finalText) {
  return withTransaction(async (client) => {
    // Kun det nyeste udkast opdateres; ældre forsøg står urørt som historik.
    const { rows } = await client.query(
      `UPDATE replies
          SET final_text = $2, status = 'sent', sent_at = now()
        WHERE id = (
          SELECT id FROM replies WHERE review_id = $1 ORDER BY created_at DESC LIMIT 1
        )
        RETURNING *`,
      [reviewId, finalText]
    );

    let reply = rows[0];

    if (!reply) {
      // Ejeren har skrevet svaret selv uden at generere et udkast først. Teksten
      // skal stadig gemmes, men model sættes til NULL — så kan man senere skelne
      // de håndskrevne svar fra dem modellen har foreslået.
      const inserted = await client.query(
        `INSERT INTO replies (review_id, draft_text, final_text, status, sent_at, model)
         VALUES ($1, $2, $2, 'sent', now(), NULL)
         RETURNING *`,
        [reviewId, finalText]
      );
      reply = inserted.rows[0];
    }

    await client.query(
      `UPDATE reviews SET status = 'answered', answered_at = now() WHERE id = $1`,
      [reviewId]
    );

    return reply;
  });
}

// Alle udkast til én anmeldelse, nyeste først.
async function listByReview(reviewId) {
  const { rows } = await query(
    "SELECT * FROM replies WHERE review_id = $1 ORDER BY created_at DESC",
    [reviewId]
  );
  return rows;
}

module.exports = { insertDraft, markSent, listByReview };
