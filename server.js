require("dotenv").config();
const express = require("express");
const path = require("path");
const {
  fetchJson,
  toPlaceSummary,
  toPlaceDetails,
  hasRequiredGenerateFields,
  draftReviewReply,
} = require("./utils");

const app = express();
const PORT = process.env.PORT || 3000;
const API_KEY = process.env.ANTHROPIC_API_KEY;
const PLACES_API_KEY = process.env.GOOGLE_PLACES_API_KEY;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

app.post("/api/generate", async (req, res) => {
  if (!API_KEY) {
    return res.status(500).json({
      error: "Mangler ANTHROPIC_API_KEY. Opret en .env-fil ud fra .env.example.",
    });
  }

  const { businessName, businessType, reviews, tone } = req.body;

  if (!hasRequiredGenerateFields(businessName, reviews)) {
    return res.status(400).json({ error: "Mangler virksomhedsnavn eller anmeldelser." });
  }

  try {
    const results = [];

    for (const review of reviews) {
      results.push(await draftReviewReply(review, { businessName, businessType, tone }, API_KEY));
    }

    res.json({ results });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// Søger en virksomhed op via Google Places API (New) Text Search, så man kan finde dens Place ID.
app.get("/api/places/search", async (req, res) => {
  if (!PLACES_API_KEY) {
    return res.status(500).json({
      error: "Mangler GOOGLE_PLACES_API_KEY i .env.",
    });
  }

  const query = (req.query.query || "").trim();
  if (!query) {
    return res.status(400).json({ error: "Mangler søgeord (query)." });
  }

  try {
    const data = await fetchJson("https://places.googleapis.com/v1/places:searchText", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
      },
      body: JSON.stringify({ textQuery: query, languageCode: "da" }),
    });

    res.json({ places: (data.places || []).map(toPlaceSummary) });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// Henter en virksomheds seneste anmeldelser via Google Places API (New) Place Details.
// OBS: Google udstiller maks. 5 anmeldelser pr. sted via denne API, uanset hvor mange stedet reelt har.
app.get("/api/places/reviews", async (req, res) => {
  if (!PLACES_API_KEY) {
    return res.status(500).json({
      error: "Mangler GOOGLE_PLACES_API_KEY i .env.",
    });
  }

  const placeId = (req.query.placeId || "").trim();
  if (!placeId) {
    return res.status(400).json({ error: "Mangler placeId." });
  }

  try {
    const data = await fetchJson(
      `https://places.googleapis.com/v1/places/${encodeURIComponent(placeId)}?languageCode=da`,
      {
        headers: {
          "X-Goog-Api-Key": PLACES_API_KEY,
          "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews",
        },
      }
    );

    res.json(toPlaceDetails(data));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Review Assistant kører på http://localhost:${PORT}`);
});
