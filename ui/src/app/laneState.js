import { laneDefinitions } from "../lib/config.js";

export function createInitialLaneVisibility() {
  return Object.fromEntries(laneDefinitions.map((lane) => [lane.id, true]));
}

export function createInitialLaneCollapsed() {
  return Object.fromEntries(laneDefinitions.map((lane) => [lane.id, false]));
}