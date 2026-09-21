// Postgres afviser selv en ugyldig UUID, men med en 22P02-fejl der bobler op
// som en 500'er — altså "serveren er i stykker", når sandheden er at kaldet var
// forkert. Vi tjekker derfor formatet før vi rører databasen.
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUuid(value) {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

module.exports = { isUuid };
