const { fetchJson } = require("../utils/http");

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

// Søger en virksomhed op via Google Places API (New) Text Search, så man kan finde dens Place ID.
async function searchPlaces(query, apiKey) {
  const data = await fetchJson("https://places.googleapis.com/v1/places:searchText", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Goog-Api-Key": apiKey,
      "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
    },
    body: JSON.stringify({ textQuery: query, languageCode: "da" }),
  });

  return (data.places || []).map(toPlaceSummary);
}

// Henter en virksomheds seneste anmeldelser via Google Places API (New) Place Details.
// OBS: Google udstiller maks. 5 anmeldelser pr. sted via denne API, uanset hvor mange stedet reelt har.
async function getPlaceDetails(placeId, apiKey) {
  const data = await fetchJson(
    `https://places.googleapis.com/v1/places/${encodeURIComponent(placeId)}?languageCode=da`,
    {
      headers: {
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews",
      },
    }
  );

  return toPlaceDetails(data);
}

module.exports = {
  searchPlaces,
  getPlaceDetails,
};
