const express = require("express");
const generateRoutes = require("./generate.routes");
const placesRoutes = require("./places.routes");
const reviewsRoutes = require("./reviews.routes");

const router = express.Router();

router.use("/api", generateRoutes);
router.use("/api", placesRoutes);
router.use("/api", reviewsRoutes);

module.exports = router;
