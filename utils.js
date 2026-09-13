// Henter en URL og parser JSON, kaster en beskrivende fejl hvis kaldet fejler.
async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API-fejl (${response.status}): ${errText}`);
  }
  return response.json();
}

// Omdanner et Places "searchText"-resultat til det format vi sender til frontenden.
function toPlaceSummary(p) {
  return {
    placeId: p.id,
    name: p.displayName?.text || "",
    address: p.formattedAddress || "",
  };
}

// Omdanner en Places-anmeldelse til det format vi sender til frontenden.
function toReviewSummary(r) {
  return {
    externalId: r.name,
    reviewerName: r.authorAttribution?.displayName || "",
    rating: r.rating,
    reviewText: r.text?.text || r.originalText?.text || "",
    publishTime: r.publishTime,
  };
}

// Omdanner et Places Details-svar til det format vi sender til frontenden.
function toPlaceDetails(data) {
  return {
    businessName: data.displayName?.text || "",
    address: data.formattedAddress || "",
    rating: data.rating,
    userRatingCount: data.userRatingCount,
    reviews: (data.reviews || []).map(toReviewSummary),
  };
}

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
  fetchJson,
  toPlaceSummary,
  toReviewSummary,
  toPlaceDetails,
  hasRequiredGenerateFields,
  draftReviewReply,
};
