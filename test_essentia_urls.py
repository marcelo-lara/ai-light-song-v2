import urllib.request
urls = [
    "https://essentia.upf.edu/models/classification-heads/msd_musicnn/msd-musicnn-1.pb",
    "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_genre/mtg_jamendo_genre-musicnn-1.pb",
    "https://essentia.upf.edu/models/music-style-classification/discogs-effnet-bs64-1.pb",
    "https://essentia.upf.edu/models/music-style-classification/msd-musicnn-1.pb"
]
for u in urls:
    try:
        r = urllib.request.urlopen(u)
        print(f"OK: {u}")
    except Exception as e:
        print(f"FAILED: {u} - {e}")
