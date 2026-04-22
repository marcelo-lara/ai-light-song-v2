import { laneDefinitions } from "./laneDefinitions.js";

export const coreArtifactKeys = ["beatsArtifact", "harmonic", "symbolic", "energy", "sectionsArtifact", "eventMachine", "validation"];
export const dynamicLaneIds = new Set(laneDefinitions.filter((lane) => lane.type === "dynamic").map((lane) => lane.id));
export const DEFAULT_ZOOM = 48;
export const MIN_ZOOM = 12;
export const MAX_ZOOM = 180;
export const LABEL_WIDTH = 220;