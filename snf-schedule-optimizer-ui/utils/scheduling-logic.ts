export const SHIFT_NAMES: ("Morning" | "Afternoon" | "Night")[] = [
  "Morning",
  "Afternoon",
  "Night",
];

export const getStartOfWeek = (date: Date): Date => {
  const day = date.getDay(); // 0 for Sunday, 1 for Monday, etc.
  const diff = day; // Days to subtract to get to Sunday (the start of the week)
  const startOfWeek = new Date(date);
  startOfWeek.setDate(date.getDate() - diff);
  startOfWeek.setHours(0, 0, 0, 0);
  return startOfWeek;
};

// Helper to get the start of the month (1st day)
export const getStartOfMonth = (date: Date): Date => {
  return new Date(date.getFullYear(), date.getMonth(), 1);
};

// Helper to format date to YYYY-MM-DD
export const formatDateYYYYMMDD = (date: Date): string => {
  const d = new Date(date);
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  const year = d.getFullYear();
  return [year, month, day].join("-");
};

export const getToday = (): Date => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
};
export const getTodayString = (): string => formatDateYYYYMMDD(getToday());
export const getWindowEnd = (): Date => {
  const windowEnd = new Date(getToday());
  windowEnd.setDate(windowEnd.getDate() + 13);
  windowEnd.setHours(23, 59, 59, 999);
  return windowEnd;
};
