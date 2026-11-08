const publicationDate = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });

// Publication dates use UTC in every browser. Unzoned times are ambiguous;
// retain them in source details rather than inventing a publication day.
export function formatPublicationDate(value) {
  if (typeof value !== "string") return null;
  const parts = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?$/);
  if (!parts) return null;
  const [, year, month, day, hour, minute, second, zone] = parts;
  const calendarDay = new Date(`${year}-${month}-${day}T00:00:00Z`);
  if (calendarDay.getUTCFullYear() !== Number(year) || calendarDay.getUTCMonth() + 1 !== Number(month) || calendarDay.getUTCDate() !== Number(day)
    || Number(hour || 0) > 23 || Number(minute || 0) > 59 || Number(second || 0) > 59
    || (zone && zone !== "Z" && (Number(zone.slice(1, 3)) > 23 || Number(zone.slice(4)) > 59))) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? `${publicationDate.format(date)} (UTC)` : null;
}
