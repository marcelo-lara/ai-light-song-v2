import { useCallback, useEffect, useState } from "preact/hooks";

import { fetchJson } from "../lib/data.js";
import { saveSongFactsFile } from "./songDataApi.js";

const reviewQueueParts = (song) => ["data", "analysis", song, "artifacts", "validation", "review_queue.json"];
const songFactsParts = (song) => ["data", "analysis", song, "reference", "human", "song_facts.json"];

// v1.1 Story 5.2 — render review_queue.json as answerable questions and save the
// answers into reference/human/song_facts.json on an explicit human save only.
//
// Only the whole-song questions (form_family, form_family_vs_genre) round-trip
// into song_facts.json; per-section form_role and drop-location questions are
// shown for context but answered by editing human_hints.json (Story 8.8).
const ANSWERABLE_FIELDS = new Set(["form_family", "form_family_vs_genre"]);

function questionToFact(field) {
  return field === "form_family_vs_genre" ? "genre" : field;
}

export function useReviewQueueEditor(selectedSong) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [existingFacts, setExistingFacts] = useState({});
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setAnswers({});
    setSaveState({ status: "idle", message: "" });
    if (!selectedSong) {
      setQuestions([]);
      return undefined;
    }
    (async () => {
      try {
        const queue = await fetchJson(reviewQueueParts(selectedSong));
        if (!cancelled) {
          setQuestions(Array.isArray(queue?.questions) ? queue.questions : []);
          setLoadError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setQuestions([]);
          setLoadError(error instanceof Error ? error.message : "No review queue for this song.");
        }
      }
      try {
        const facts = await fetchJson(songFactsParts(selectedSong));
        if (!cancelled) {
          setExistingFacts(facts?.facts && typeof facts.facts === "object" ? facts.facts : {});
        }
      } catch {
        if (!cancelled) {
          setExistingFacts({});
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedSong]);

  const answerable = questions.filter((question) => ANSWERABLE_FIELDS.has(question.field));

  const setAnswer = useCallback((field, value) => {
    setAnswers((current) => ({ ...current, [field]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedSong) {
      return;
    }
    const facts = {};
    for (const [field, value] of Object.entries(answers)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      facts[questionToFact(field)] = { value };
    }
    if (Object.keys(facts).length === 0) {
      setSaveState({ status: "error", message: "Choose an answer before saving." });
      return;
    }
    setSaveState({ status: "saving", message: "Saving song_facts.json…" });
    try {
      const saved = await saveSongFactsFile(selectedSong, { song_name: selectedSong, facts });
      setExistingFacts(saved?.facts || {});
      setAnswers({});
      setSaveState({ status: "success", message: "Saved. Re-run the analyzer to apply." });
    } catch (error) {
      setSaveState({ status: "error", message: error instanceof Error ? error.message : "Save failed." });
    }
  }, [answers, selectedSong]);

  return { questions, answerable, answers, existingFacts, loadError, saveState, setAnswer, handleSave };
}
