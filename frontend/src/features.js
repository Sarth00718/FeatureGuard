// Form field definitions. Ranges here are only UI hints - the API enforces the real rules.
export const FIELDS = [
  { name: "fixed_acidity", label: "Fixed acidity", example: 7.4, step: 0.1 },
  { name: "volatile_acidity", label: "Volatile acidity", example: 0.7, step: 0.01 },
  { name: "citric_acid", label: "Citric acid", example: 0.0, step: 0.01 },
  { name: "residual_sugar", label: "Residual sugar", example: 1.9, step: 0.1 },
  { name: "chlorides", label: "Chlorides", example: 0.076, step: 0.001 },
  { name: "free_sulfur_dioxide", label: "Free sulfur dioxide", example: 11, step: 1 },
  { name: "total_sulfur_dioxide", label: "Total sulfur dioxide", example: 34, step: 1 },
  { name: "density", label: "Density", example: 0.9978, step: 0.0001 },
  { name: "ph", label: "pH", example: 3.51, step: 0.01 },
  { name: "sulphates", label: "Sulphates", example: 0.56, step: 0.01 },
  { name: "alcohol", label: "Alcohol (%)", example: 9.4, step: 0.1 },
];

export function exampleValues() {
  return Object.fromEntries(FIELDS.map((f) => [f.name, String(f.example)]));
}

// Convert the string values of the form into numbers. Empty/invalid text stays as a string
// on purpose, so the API (not the UI) rejects it with a clear message.
export function toPayload(values) {
  return Object.fromEntries(
    Object.entries(values).map(([k, v]) => {
      const trimmed = String(v).trim();
      const n = Number(trimmed);
      return [k, trimmed !== "" && Number.isFinite(n) ? n : trimmed];
    })
  );
}
