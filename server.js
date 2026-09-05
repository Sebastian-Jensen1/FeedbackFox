require("dotenv").config();
const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const API_KEY = process.env.ANTHROPIC_API_KEY;
const PLACES_API_KEY = process.env.GOOGLE_PLACES_API_KEY;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

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

app.post("/api/generate", async (req, res) => {
  if (!API_KEY) {
    return res.status(500).json({
      error: "Mangler ANTHROPIC_API_KEY. Opret en .env-fil ud fra .env.example.",
    });
  }

  const { businessName, businessType, reviews, tone } = req.body;

  if (!businessName || !Array.isArray(reviews) || reviews.length === 0) {
    return res.status(400).json({ error: "Mangler virksomhedsnavn eller anmeldelser." });
  }

  try {
    const results = [];

    for (const review of reviews) {
      const prompt = buildPrompt({
        businessName,
        businessType,
        reviewerName: review.reviewerName,
        rating: review.rating,
        reviewText: review.reviewText,
        tone,
      });

      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: "claude-sonnet-4-6",
          max_tokens: 300,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Anthropic API-fejl (${response.status}): ${errText}`);
      }

      const data = await response.json();
      const draft = data.content?.find((c) => c.type === "text")?.text?.trim() || "";

      results.push({
        id: review.id,
        reviewerName: review.reviewerName,
        rating: review.rating,
        reviewText: review.reviewText,
        draft,
      });
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
    const response = await fetch("https://places.googleapis.com/v1/places:searchText", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
      },
      body: JSON.stringify({ textQuery: query, languageCode: "da" }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Places API-fejl (${response.status}): ${errText}`);
    }

    const data = await response.json();
    const places = (data.places || []).map((p) => ({
      placeId: p.id,
      name: p.displayName?.text || "",
      address: p.formattedAddress || "",
    }));

    res.json({ places });
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
    const response = await fetch(
      `https://places.googleapis.com/v1/places/${encodeURIComponent(placeId)}?languageCode=da`,
      {
        headers: {
          "X-Goog-Api-Key": PLACES_API_KEY,
          "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews",
        },
      }
    );

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Places API-fejl (${response.status}): ${errText}`);
    }

    const data = await response.json();
    const reviews = (data.reviews || []).map((r) => ({
      externalId: r.name,
      reviewerName: r.authorAttribution?.displayName || "",
      rating: r.rating,
      reviewText: r.text?.text || r.originalText?.text || "",
      publishTime: r.publishTime,
    }));

    res.json({
      businessName: data.displayName?.text || "",
      address: data.formattedAddress || "",
      rating: data.rating,
      userRatingCount: data.userRatingCount,
      reviews,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Review Assistant kører på http://localhost:${PORT}`);
});
