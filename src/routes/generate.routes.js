const express = require("express");
const { ANTHROPIC_API_KEY } = require("../config/env");
const { hasRequiredGenerateFields, draftReviewReply } = require("../services/claude.service");

const router = express.Router();

router.post("/generate", async (req, res) => {
  if (!ANTHROPIC_API_KEY) {
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
      results.push(await draftReviewReply(review, { businessName, businessType, tone }, ANTHROPIC_API_KEY));
    }

    res.json({ results });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
