const { fetchJson } = require("../utils/http");

// Tjekker at der er sendt et virksomhedsnavn og mindst én anmeldelse.
function hasRequiredGenerateFields(businessName, reviews) {
  return Boolean(businessName) && Array.isArray(reviews) && reviews.length > 0;
}

// Bygger den prompt som sendes til Claude for hvert anmeldelse.
function buildPrompt({ businessName, businessType, reviewerName, rating, reviewText, tone }) {
  return `Du skriver et kort svar på en Google-anmeldelse på vegne af en dansk virksomhed.

Virksomhed: ${businessName} (${businessType || "lokal virksomhed"})
Anmelder: ${reviewerName || "kunden"}
Stjerner: ${rating || "ukendt"}/5
Anmeldelsens tekst: "${reviewText}"

Skriv et svar der:
- er på dansk, ${tone || "venligt og professionelt"} i tonen
- hvis review er på engelsk eller hvilket som helst andet sprog end dansk, svares der på engelsk
- forholder sig konkret til det anmelderen faktisk skriver (ikke generisk)
- er kort (2-5 sætninger)
- takker for anmeldelsen, og hvis den er negativ: anerkender problemet og inviterer til dialog uden at være undskyldende i overdrevent omfang
- IKKE opdigter fakta, løfter eller navne der ikke er nævnt

Svar KUN med selve svarteksten, ingen forklaring eller anførselstegn omkring.`;
}

// Udtrækker Claudes svartekst fra Messages API-svaret.
function extractDraftText(data) {
  const textBlock = data.content?.find((c) => c.type === "text");
  return textBlock?.text?.trim() || "";
}

// Bygger prompt, kalder Claude for én anmeldelse, og returnerer resultatet klar til frontenden.
async function draftReviewReply(review, { businessName, businessType, tone }, apiKey) {
  const prompt = buildPrompt({
    businessName,
    businessType,
    reviewerName: review.reviewerName,
    rating: review.rating,
    reviewText: review.reviewText,
    tone,
  });

  const data = await fetchJson("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 300,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  return {
    id: review.id,
    reviewerName: review.reviewerName,
    rating: review.rating,
    reviewText: review.reviewText,
    draft: extractDraftText(data),
  };
}

module.exports = {
  hasRequiredGenerateFields,
  draftReviewReply,
};
