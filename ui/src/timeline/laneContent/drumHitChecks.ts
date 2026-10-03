// drumHitChecks.ts — Clap Events, Kick Check, Crash Check (v3.9 item 2 and
// the "crash over-fires on bright hats/rides" bug). All three are point
// events on the drums stem, classified by per-hit spectral shape
// (`experiments/drum_hit_shape.py`), never omnizart's own label. Each block
// is drawn with a minimum width (`MIN_WIDTH_S`) — a point event, not a span.

import type { ClapEventsFile, CrashCheckFile, KickAttacksFile, KickCheckFile } from "../../data/sparseArtifacts";
import type { SparseBlock } from "../laneContent";
import { formatRange, round } from "./shared";

const MIN_WIDTH_S = 0.1;

/**
 * Claps detected from the drums stem by spectral shape — `experiments/clap_events`.
 * Every row is a proposal (a detection), never a rejected candidate: rejected
 * onsets never reach this file.
 */
export function clapEventsContent(file: ClapEventsFile | null): SparseBlock[] {
  return (file?.events ?? []).map((e, i) => buildClapBlock(e, i));
}

function buildClapBlock(e: { time: number; noise_share: number; body_share: number; confidence: number | null }, i: number): SparseBlock {
  const id = `clap-events-${i + 1}`;
  return {
    id,
    start_s: e.time,
    end_s: e.time + MIN_WIDTH_S,
    label: "clap",
    wideLabel: `clap · noise ${round(e.noise_share, 2)} · body ${round(e.body_share, 2)}`,
    laneLabel: "Clap Events",
    caption: `${formatRange(e.time, e.time)} · noise ${round(e.noise_share, 2)} · body ${round(e.body_share, 2)}`,
    reference: id,
    detail: `confidence ${e.confidence == null ? "no confidence reported" : round(e.confidence, 2)}`,
    summary: "experiments/clap_events — 1-6 kHz noise share / 120-400 Hz body share over drums-stem onset candidates. Proposal to audition against Human Hints.",
    raw: e,
  };
}

/**
 * Every omnizart `kick` kept or rejected by the same per-hit shape plus a
 * percussive-attack gate — `experiments/kick_check`. `verdict` distinguishes
 * keep/reject via `tintId`.
 */
export function kickCheckContent(file: KickCheckFile | null): SparseBlock[] {
  return (file?.kicks ?? []).map((k, i) => buildKickBlock(k, i));
}

function buildKickBlock(k: { time: number; verdict: string; low_share: number; noise_share: number }, i: number): SparseBlock {
  const id = `kick-check-${i + 1}`;
  const kept = k.verdict === "keep";
  return {
    id,
    start_s: k.time,
    end_s: k.time + MIN_WIDTH_S,
    label: kept ? "kick" : "reject",
    wideLabel: `${k.verdict} · low ${round(k.low_share, 2)} · noise ${round(k.noise_share, 2)}`,
    laneLabel: "Kick Check",
    caption: `${formatRange(k.time, k.time)} · ${k.verdict} · low ${round(k.low_share, 2)} · noise ${round(k.noise_share, 2)}`,
    reference: id,
    detail: `omnizart kick at ${round(k.time, 2)}s`,
    summary: "experiments/kick_check — sub/low body share + 1-6 kHz noise share + percussive-attack gate over every omnizart `kick` event. Proposal to audition, not a published verdict.",
    raw: k,
    tintId: kept ? "kickCheckKeep" : "kickCheckReject",
  };
}

/**
 * Kick attacks detected on the mix — `experiments/kick_attacks`. Echo rows (weaker, duller
 * repeats at a recurring offset) are labelled `echo` and tinted grey; an attack beyond 1/4
 * beat from the beat grid keeps its event at reduced confidence and is tinted dusky.
 * A proposal to audition, not truth.
 */
export function kickAttacksContent(file: KickAttacksFile | null): SparseBlock[] {
  return (file?.events ?? []).map((e, i) => {
    const id = `kick-attacks-${i + 1}`;
    const echo = e.echo_of != null;
    const conf = e.confidence == null ? "no confidence reported" : `confidence ${round(e.confidence, 2)}`;
    const grid = e.grid === "untrusted" ? "grid untrusted" : e.on_grid ? "on grid" : "off grid";
    const ev = `rise ${e.rise_db == null ? "n/a" : round(e.rise_db, 1)} dB · click ${e.click_db == null ? "n/a" : round(e.click_db, 1)} dB`;
    return {
      id,
      start_s: e.time,
      end_s: e.time + MIN_WIDTH_S,
      label: echo ? "echo" : "kick",
      wideLabel: echo ? `echo of ${round(e.echo_of as number, 2)}s` : `kick · ${conf}`,
      laneLabel: "Kick Attacks",
      caption: `${formatRange(e.time, e.time)} · ${echo ? "echo" : "kick"} · ${conf} · ${grid}`,
      reference: id,
      detail: `${ev}${e.pitch_drop ? " · pitch drop" : ""}`,
      summary: "experiments/kick_attacks — steep 40-120 Hz rise with a coincident 2-5 kHz click on the mix; weaker+duller repeats at a recurring offset labelled echo; off-grid kept at low confidence. Proposal to audition, not truth.",
      raw: e,
      tintId: echo ? "kickAttacksEcho" : e.on_grid || e.grid === "untrusted" ? "kickAttacks" : "kickAttacksOffGrid",
    };
  });
}

/**
 * Every omnizart `crash` kept or rejected by regular-stream-period rejection
 * plus a brilliance-band decay-shape gate — `experiments/crash_check`.
 * `verdict` distinguishes keep/reject via `tintId`.
 */
export function crashCheckContent(file: CrashCheckFile | null): SparseBlock[] {
  return (file?.crashes ?? []).map((c, i) => buildCrashBlock(c, i));
}

function buildCrashBlock(
  c: { time: number; verdict: string; is_stream_continuation: boolean; decay_ratio: number | null },
  i: number,
): SparseBlock {
  const id = `crash-check-${i + 1}`;
  const kept = c.verdict === "keep";
  const decayText = c.decay_ratio == null ? "no decay reading" : `decay ${round(c.decay_ratio, 2)}`;
  return {
    id,
    start_s: c.time,
    end_s: c.time + MIN_WIDTH_S,
    label: kept ? "crash" : "reject",
    wideLabel: `${c.verdict} · ${c.is_stream_continuation ? "stream member" : "isolated"} · ${decayText}`,
    laneLabel: "Crash Check",
    caption: `${formatRange(c.time, c.time)} · ${c.verdict} · ${c.is_stream_continuation ? "stream member" : "isolated"} · ${decayText}`,
    reference: id,
    detail: `omnizart crash at ${round(c.time, 2)}s`,
    summary: "experiments/crash_check — regular-stream-period rejection (~1-2 beat spacing) + brilliance-band decay-shape gate over every omnizart `crash` event. Proposal to audition, not a published verdict.",
    raw: c,
    tintId: kept ? "crashCheckKeep" : "crashCheckReject",
  };
}
