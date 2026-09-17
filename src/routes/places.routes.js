const express = require("express");
const { GOOGLE_PLACES_API_KEY } = require("../config/env");
const { searchPlaces, getPlaceDetails } = require("../services/places.service");

const router = express.Router();

router.get("/places/search", async (req, res) => {
  if (!GOOGLE_PLACES_API_KEY) {
    return res.status(500).json({
      error: "Mangler GOOGLE_PLACES_API_KEY i .env.",
    });
  }

  const query = (req.query.query || "").trim();
  if (!query) {
    return res.status(400).json({ error: "Mangler søgeord (query)." });
  }

  try {
    const places = await searchPlaces(query, GOOGLE_PLACES_API_KEY);
    res.json({ places });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});


router.get("/places/reviews", async (req, res) => {
  if (!GOOGLE_PLACES_API_KEY) {
    return res.status(500).json({
      error: "Mangler GOOGLE_PLACES_API_KEY i .env.",
    });
  }

  const placeId = (req.query.placeId || "").trim();
  if (!placeId) {
    return res.status(400).json({ error: "Mangler placeId." });
  }

  try {
    const details = await getPlaceDetails(placeId, GOOGLE_PLACES_API_KEY);
    res.json(details);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
