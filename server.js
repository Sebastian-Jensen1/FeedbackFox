const app = require("./src/app");
const { PORT } = require("./src/config/env");

app.listen(PORT, () => {
  console.log(`Review Assistant kører på http://localhost:${PORT}`);
});
