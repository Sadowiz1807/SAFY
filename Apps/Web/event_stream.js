import { safyState, applyPatch } from "./state.js";
export function applyEvent(event) { safyState.events.push(event); if (event && event.payload && event.payload.ui_patch) applyPatch(event.payload.ui_patch); return safyState; }
