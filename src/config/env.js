require("dotenv").config();

module.exports = {
  PORT: process.env.PORT || 3000,
  ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
  GOOGLE_PLACES_API_KEY: process.env.GOOGLE_PLACES_API_KEY,
  DATABASE_URL: process.env.DATABASE_URL,
};
