export const probability = (value: number) => `${(value * 100).toFixed(1)}%`;

export const percentile = (value: number) => `${(value * 100).toFixed(1)}th`;

export const monthLabel = (value: string) => {
  const [year, month] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
};

export const reported = (value: string | null) => value || "Not reported";

export const modelLabel = (model: string) =>
  model.startsWith("catboost") ? "CatBoost · locked" : "Logistic · locked";
