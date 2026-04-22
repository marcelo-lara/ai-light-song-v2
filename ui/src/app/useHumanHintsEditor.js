import { useEffect, useRef, useState } from "preact/hooks";

function formatEditableTime(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "0";
  }
  return String(numeric);
}

function normalizeDraftHint(hint, index) {
  return {
    id: String(hint?.id ?? `human-hint-${index + 1}`),
    title: String(hint?.title ?? hint?.label ?? `Hint ${index + 1}`),
    start_time: formatEditableTime(hint?.start_time ?? hint?.start_s ?? hint?.start ?? 0),
    end_time: formatEditableTime(hint?.end_time ?? hint?.end_s ?? hint?.end ?? 0),
    summary: typeof hint?.summary === "string" ? hint.summary : "",
    lighting_hint: typeof hint?.lighting_hint === "string" ? hint.lighting_hint : "",
  };
}

function parseSnapshot(songName, humanHintsFile) {
  const humanHints = Array.isArray(humanHintsFile?.human_hints) ? humanHintsFile.human_hints : [];
  return {
    song_name: String(humanHintsFile?.song_name || songName || ""),
    human_hints: humanHints.map(normalizeDraftHint),
  };
}

function buildSavePayload(songName, hints) {
  const normalizedHints = hints.map((hint) => {
    const startTime = Number(hint.start_time);
    const endTime = Number(hint.end_time);
    if (!hint.id.trim()) {
      throw new Error("Each human hint must include an id before saving.");
    }
    if (!hint.title.trim()) {
      throw new Error("Each human hint must include a title before saving.");
    }
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) {
      throw new Error("Human hint start and end times must be valid numbers.");
    }
    if (endTime < startTime) {
      throw new Error("Human hint end time must be greater than or equal to start time.");
    }
    return {
      id: hint.id.trim(),
      title: hint.title.trim(),
      start_time: startTime,
      end_time: endTime,
      summary: hint.summary.trim(),
      lighting_hint: hint.lighting_hint.trim(),
    };
  });

  return {
    song_name: String(songName || ""),
    human_hints: normalizedHints,
  };
}

function createNewHint(currentTime, existingHints) {
  const nextIndex = existingHints.length + 1;
  return {
    id: `human-hint-${Date.now()}`,
    title: `Hint ${nextIndex}`,
    start_time: formatEditableTime(currentTime),
    end_time: formatEditableTime(currentTime),
    summary: "",
    lighting_hint: "",
  };
}

function findHintIdFromSelection(selection, hints) {
  if (!selection || selection.laneLabel !== "Human Hints") {
    return "";
  }
  const candidateIds = [selection.reference, selection.detail, selection.label]
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  const match = hints.find((hint) => candidateIds.includes(hint.id) || candidateIds.includes(hint.title));
  return match?.id || "";
}

export function useHumanHintsEditor({
  selectedSong,
  humanHintsFile,
  selectedRegion,
  currentTime,
  onSave,
  onCancelSelection,
}) {
  const baseSignatureRef = useRef("");
  const selectedSongRef = useRef("");

  const [songName, setSongName] = useState("");
  const [hints, setHints] = useState([]);
  const [activeHintId, setActiveHintId] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  useEffect(() => {
    if (!selectedSong) {
      baseSignatureRef.current = "";
      selectedSongRef.current = "";
      setSongName("");
      setHints([]);
      setActiveHintId("");
      setIsOpen(false);
      setSaveState({ status: "idle", message: "" });
      return;
    }

    const nextSnapshot = parseSnapshot(selectedSong, humanHintsFile);
    const nextSignature = JSON.stringify(nextSnapshot);
    if (selectedSongRef.current === selectedSong && baseSignatureRef.current === nextSignature) {
      return;
    }

    selectedSongRef.current = selectedSong;
    baseSignatureRef.current = nextSignature;
    setSongName(nextSnapshot.song_name);
    setHints(nextSnapshot.human_hints);
    setActiveHintId("");
    setIsOpen(false);
    setSaveState({ status: "idle", message: "" });
  }, [humanHintsFile, selectedSong]);

  useEffect(() => {
    const nextActiveHintId = findHintIdFromSelection(selectedRegion, hints);
    if (!nextActiveHintId) {
      return;
    }
    setActiveHintId(nextActiveHintId);
    setIsOpen(true);
    setSaveState({ status: "idle", message: "" });
  }, [hints, selectedRegion]);

  const activeHint = hints.find((hint) => hint.id === activeHintId) || null;

  function handleChangeActiveHint(field, value) {
    setHints((currentHints) => currentHints.map((hint) => hint.id === activeHintId ? { ...hint, [field]: value } : hint));
    setSaveState({ status: "idle", message: "" });
  }

  function handleAddHint() {
    const nextHint = createNewHint(currentTime, hints);
    setHints((currentHints) => [...currentHints, nextHint]);
    setActiveHintId(nextHint.id);
    setIsOpen(true);
    setSaveState({ status: "idle", message: "" });
  }

  function handleSetTime(field) {
    handleChangeActiveHint(field, formatEditableTime(currentTime));
  }

  function handleDeleteActiveHint() {
    if (!activeHintId) {
      return;
    }
    setHints((currentHints) => {
      return currentHints.filter((hint) => hint.id !== activeHintId);
    });
    setActiveHintId("");
    setIsOpen(false);
    setSaveState({ status: "idle", message: "" });
    onCancelSelection?.();
  }

  function handleCancel() {
    const nextSnapshot = parseSnapshot(selectedSong, humanHintsFile);
    setSongName(nextSnapshot.song_name);
    setHints(nextSnapshot.human_hints);
    setActiveHintId("");
    setIsOpen(false);
    setSaveState({ status: "idle", message: "" });
    onCancelSelection?.();
  }

  async function handleSave() {
    try {
      const payload = buildSavePayload(songName || selectedSong, hints);
      await onSave?.(payload);
      const nextSignature = JSON.stringify(payload);
      baseSignatureRef.current = nextSignature;
      selectedSongRef.current = selectedSong;
      setSongName(payload.song_name);
      setHints(payload.human_hints.map(normalizeDraftHint));
      setSaveState({ status: "success", message: "Human hints saved to the reference file." });
    } catch (error) {
      setSaveState({ status: "error", message: error instanceof Error ? error.message : "Unable to save human hints." });
    }
  }

  return {
    selectedSong,
    currentTime,
    isOpen,
    activeHint,
    hints,
    saveState,
    handleAddHint,
    handleCancel,
    handleChangeActiveHint,
    handleDeleteActiveHint,
    handleSave,
    handleSetStartTime() { handleSetTime("start_time"); },
    handleSetEndTime() { handleSetTime("end_time"); },
  };
}