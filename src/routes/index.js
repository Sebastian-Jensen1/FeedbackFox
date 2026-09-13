const express = require("express");
const generateRoutes = require("./generate.routes");
const placesRoutes = require("./places.routes");

const router = express.Router();

router.use("/api", generateRoutes);
router.use("/api", placesRoutes);

module.exports = router;
