const express = require("express");
const restaurants = require("../models/restaurants.model");
const reviews = require("../models/reviews.model");
const replies = require("../models/replies.model");
const { isUuid } = require("../utils/validation");

const router = express.Router();

// Bruges når siden åbnes: findes der allerede et sted i databasen, indlæses det
// i stedet for at starte på en tom liste.
router.get("/restaurants", async (req, res) => {
  try {
    const rows = await restaurants.listAll();
    res.json({
      restaurants: rows.map((r) => ({
        id: r.id,
        name: r.name,
        businessType: r.business_type || "",
        address: r.address || "",
        defaultTone: r.default_tone || "",
      })),
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

router.get("/restaurants/:id/reviews", async (req, res) => {
  const { id } = req.params;
  if (!isUuid(id)) {
    return res.status(400).json({ error: "Ugyldigt restaurant-id." });
  }

  try {
    const restaurant = await restaurants.findById(id);
    if (!restaurant) {
      return res.status(404).json({ error: "Restauranten findes ikke." });
    }

    const rows = await reviews.listByRestaurant(id);
    res.json({
      restaurantId: restaurant.id,
      businessName: restaurant.name,
      businessType: restaurant.business_type || "",
      defaultTone: restaurant.default_tone || "",
      reviews: rows.map(reviews.toClientReview),
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// "Send til Google": gemmer den tekst ejeren faktisk sendte — som kan være
// redigeret i forhold til udkastet — og flytter anmeldelsen til "Besvarede".
router.post("/reviews/:id/send", async (req, res) => {
  const { id } = req.params;
  if (!isUuid(id)) {
    return res.status(400).json({ error: "Ugyldigt anmeldelses-id." });
  }

  const finalText = (req.body?.finalText || "").trim();
  if (!finalText) {
    return res.status(400).json({ error: "Mangler svartekst." });
  }

  try {
    const review = await reviews.findById(id);
    if (!review) {
      return res.status(404).json({ error: "Anmeldelsen findes ikke." });
    }

    await replies.markSent(id, finalText);
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// "Markér som besvaret": ejeren har svaret ude på Google i forvejen, så der er
// ingen tekst at gemme — kun status skal flyttes.
router.post("/reviews/:id/answered", async (req, res) => {
  const { id } = req.params;
  if (!isUuid(id)) {
    return res.status(400).json({ error: "Ugyldigt anmeldelses-id." });
  }

  try {
    const updated = await reviews.markAnswered(id);
    if (!updated) {
      return res.status(404).json({ error: "Anmeldelsen findes ikke." });
    }
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
