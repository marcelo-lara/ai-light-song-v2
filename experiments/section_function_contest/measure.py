import json, math, os

ROOT = "/data/analysis"
DRUMS_MARGIN_DB = 3.0
MIX_MIN_GAP_DB = -1.5
PLAY_TOLERANCE = -1
FCONF_CEIL = 0.9

def mean(xs):
    xs = list(xs)
    return sum(xs)/len(xs) if xs else 0.0

def db(x):
    return 20.0*math.log10(max(x, 1e-9))

def analyse():
    table = []
    flags = []
    songs = sorted(os.listdir(ROOT))
    n_analysed = 0
    n_skipped = []
    for song in songs:
        d = os.path.join(ROOT, song)
        lp, sp, ap = (os.path.join(d, f) for f in ("loudness.json", "sections.json", "arrangement_state.json"))
        if not (os.path.isfile(lp) and os.path.isfile(sp)):
            n_skipped.append(song); continue
        n_analysed += 1
        L = json.load(open(lp)); S = json.load(open(sp))["sections"]
        order = L["metadata"]["source_order"]; ix = {n: order.index(n) for n in order}
        frames = L["frames"]
        A = json.load(open(ap))["blocks"] if os.path.isfile(ap) else []
        def pc(t):
            b = None
            for blk in A:
                if blk["start_s"] <= t < blk["end_s"]: b = blk
            return len(b["playing"]) if b else (len(A[-1]["playing"]) if A else 0)
        secs = []
        for s in S:
            a, b = float(s["start"]), float(s["end"])
            fr = [f for f in frames if a <= f["time"] < b]
            if not fr: continue
            secs.append(dict(id=s["section_id"], fn=s.get("function"), fc=s.get("function_confidence"),
                             a=a, b=b, mix=mean(f["values"][ix["mix"]] for f in fr),
                             dr=mean(f["values"][ix["drums"]] for f in fr), pc=pc((a+b)/2)))
        for i, s in enumerate(secs):
            nx = secs[i+1] if i+1 < len(secs) else None
            contested, margin = False, None
            if nx:
                mix_gap = db(nx["mix"]) - db(s["mix"])
                dr_gap = db(nx["dr"]) - db(s["dr"])
                play_gap = nx["pc"] - s["pc"]
                margin = round(dr_gap, 2)
                contested = (s["fn"] == "chorus" and nx["fn"] in ("verse", "bridge")
                             and (s["fc"] is None or s["fc"] <= FCONF_CEIL)
                             and dr_gap >= DRUMS_MARGIN_DB and mix_gap >= MIX_MIN_GAP_DB
                             and play_gap >= PLAY_TOLERANCE)
                row = (f"{song} | {s['id']} {s['fn']} fc={s['fc']} mix={s['mix']:.4f} dr={s['dr']:.4f} pc={s['pc']}"
                       f"  -> {nx['id']} {nx['fn']}: mix_gap={mix_gap:+.2f} dr_gap={dr_gap:+.2f} play_gap={play_gap:+d}"
                       f"{'   *** CONTESTED' if contested else ''}")
            else:
                row = f"{song} | {s['id']} {s['fn']} fc={s['fc']} mix={s['mix']:.4f} dr={s['dr']:.4f} pc={s['pc']}  (last)"
            table.append(row)
            if contested: flags.append((song, s["id"], s["fn"], margin))
    return table, flags, n_analysed, n_skipped

table, flags, n_analysed, n_skipped = analyse()
print("\n".join(table))
print(f"\n\n=== {n_analysed} songs analysed; skipped (no loudness/sections): {n_skipped or 'none'} ===")
print(f"=== {len(flags)} section(s) flagged across {len(set(f[0] for f in flags))} song(s) ===")
for f in flags: print("   ", f)
