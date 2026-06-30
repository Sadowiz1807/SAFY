export const safyState = { session: null, rules: [], execute: { sql: "", check: null }, events: [] };
export function applyPatch(patch) { if (!patch || !patch.target) return safyState; safyState[patch.target] = patch.value; return safyState; }
