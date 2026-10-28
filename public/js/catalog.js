// Older catalog titles re-enter Netflix's Top 10 too; the storm list tags them and lists this-or-recent releases first.
export const CATALOG_YEARS = 5;

/** True when a title's release year is more than CATALOG_YEARS before the data week's year. No known year: not tagged. */
export const isCatalogTitle = (year, dataYear) => Number.isFinite(year) && Number.isFinite(dataYear) && dataYear - year > CATALOG_YEARS;
