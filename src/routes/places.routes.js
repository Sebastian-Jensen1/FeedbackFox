const express = require("express");
const { GOOGLE_PLACES_API_KEY } = require("../config/env");
const { searchPlaces, getPlaceDetails } = require("../services/places.service");
const restaurants = require("../models/restaurants.model");
const reviews = require("../models/reviews.model");

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


// Henter fra Google OG gemmer i databasen. Svaret kommer fra databasen, ikke fra
// Google: kun sådan får frontenden de rigtige id'er, og den status og de udkast
// der allerede ligger på anmeldelser man har hentet før.
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

  const businessType = (req.query.businessType || "").trim();

  try {
    const details = await getPlaceDetails(placeId, GOOGLE_PLACES_API_KEY);

    const restaurant = await restaurants.upsertByPlaceId({
      googlePlaceId: placeId,
      name: details.businessName,
      businessType,
      address: details.address,
      googleRating: details.rating,
      googleRatingCount: details.userRatingCount,
    });

    await reviews.upsertMany(restaurant.id, details.reviews);

    // Bevidst en frisk oplæsning frem for at bruge rækkerne fra upsert: listen
    // skal indeholde ALT vi har på stedet, også anmeldelser fra tidligere
    // hentninger som Google ikke længere sender med i sine fem.
    const rows = await reviews.listByRestaurant(restaurant.id);

    res.json({
      restaurantId: restaurant.id,
      businessName: restaurant.name,
      businessType: restaurant.business_type || "",
      address: restaurant.address || "",
      rating: restaurant.google_rating,
      userRatingCount: restaurant.google_rating_count,
      defaultTone: restaurant.default_tone || "",
      reviews: rows.map(reviews.toClientReview),
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
