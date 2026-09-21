const express = require("express");
const { ANTHROPIC_API_KEY } = require("../config/env");
const { hasRequiredGenerateFields, draftReviewReply } = require("../services/claude.service");
const restaurants = require("../models/restaurants.model");
const replies = require("../models/replies.model");
const { isUuid } = require("../utils/validation");

const router = express.Router();

router.post("/generate", async (req, res) => {
  if (!ANTHROPIC_API_KEY) {
    return res.status(500).json({
      error: "Mangler ANTHROPIC_API_KEY. Opret en .env-fil ud fra .env.example.",
    });
  }

  const { businessName, businessType, reviews, tone, restaurantId } = req.body;

  if (!hasRequiredGenerateFields(businessName, reviews)) {
    return res.status(400).json({ error: "Mangler virksomhedsnavn eller anmeldelser." });
  }

  // Alle id'er tjekkes før det første kald til Claude. Ellers ville vi nå at
  // betale for udkast som bagefter ikke kan gemmes.
  if (!reviews.every((review) => isUuid(review.id))) {
    return res.status(400).json({ error: "En eller flere anmeldelser mangler et gyldigt id." });
  }

  try {
    if (restaurantId && isUuid(restaurantId) && tone) {
      await restaurants.updateDefaultTone(restaurantId, tone);
    }

    const results = [];

    for (const review of reviews) {
      const result = await draftReviewReply(
        review,
        { businessName, businessType, tone },
        ANTHROPIC_API_KEY
      );

      // Gemmes med det samme, ét udkast ad gangen. Falder noget fra hinanden
      // halvvejs i en stak på fem, er de første fire stadig gemt — og de er
      // betalt for, så de skal ikke smides væk.
      await replies.insertDraft({
        reviewId: review.id,
        draftText: result.draft,
        tone,
        model: result.model,
      });

      results.push(result);
    }

    res.json({ results });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
