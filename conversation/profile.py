"""Tiny local memory of the caller: topic/genre counts plus Markov transition tables
(what usually follows what). Stores counts only, never the words you said."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "profile.json"

TOPICS = {
    "music": ["music", "song", "album", "singer", "concert", "playlist"],
    "sports": ["football", "soccer", "match", "league", "basketball", "athlete"],
    "tech": ["code", "coding", "software", "app", "python", "website", "computer", "ai"],
    "business": ["business", "client", "money", "market", "startup", "invoice"],
    "food": ["food", "cook", "recipe", "eat", "restaurant"],
    "travel": ["travel", "trip", "flight", "visit", "holiday"],
    "movies": ["movie", "film", "series", "netflix", "actor"],
    "school": ["school", "study", "exam", "class", "learn"],
    "stories": ["story", "joke", "riddle"],
}
GENRES = ["jazz", "gospel", "afrobeat", "hip hop", "rap", "reggae", "rock", "pop", "classical", "country", "blues", "r&b"]
LAUGH = re.compile(r"\b(?:ha[\s,!.-]*){2,}|\bhehe|\blol\b|\blaugh", re.I)


TEXT_MOOD = [
    ("low", re.compile(r"\b(tired|sleepy|exhausted|sad|upset|stressed)\b", re.I)),
    ("excited", re.compile(r"\b(excited|amazing|awesome|can't wait|so happy|great news)\b", re.I)),
]


def text_mood(text: str):
    for label, rx in TEXT_MOOD:
        if rx.search(text):
            return label
    return None


def is_laughing(text: str) -> bool:
    return bool(LAUGH.search(text))


class Profile:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.topics, self.genres = Counter(), Counter()
        self.topic_next = defaultdict(Counter)
        self.mood_next = defaultdict(Counter)
        self.last_topic = self.last_mood = None
        if self.path and self.path.exists():
            try:
                d = json.loads(self.path.read_text())
                self.topics, self.genres = Counter(d["topics"]), Counter(d["genres"])
                self.topic_next = defaultdict(Counter, {k: Counter(v) for k, v in d["topic_next"].items()})
                self.mood_next = defaultdict(Counter, {k: Counter(v) for k, v in d["mood_next"].items()})
            except Exception:
                pass

    def observe(self, text: str, mood: str = "neutral"):
        t = text.lower()
        for topic, words in TOPICS.items():
            if any(re.search(rf"\b{re.escape(w)}", t) for w in words):
                self.topics[topic] += 1
                if self.last_topic:
                    self.topic_next[self.last_topic][topic] += 1
                self.last_topic = topic
        for g in GENRES:
            if re.search(rf"\b{re.escape(g)}\b", t):
                self.genres[g] += 1
        if self.last_mood:
            self.mood_next[self.last_mood][mood] += 1
        self.last_mood = mood
        self.save()

    @staticmethod
    def likely(table, prev, min_n=3, min_p=0.5):
        row = table.get(prev)
        if not row or sum(row.values()) < min_n:
            return None
        nxt, c = row.most_common(1)[0]
        return nxt if c / sum(row.values()) >= min_p else None

    def summary(self) -> str:
        parts = []
        fav = [k for k, c in self.topics.most_common(2) if c >= 3]
        if fav:
            parts.append("The caller often talks about " + " and ".join(fav) + ".")
        if self.genres and self.genres.most_common(1)[0][1] >= 2:
            parts.append(f"Their favourite music seems to be {self.genres.most_common(1)[0][0]}.")
        nxt = self.likely(self.topic_next, self.last_topic) if self.last_topic else None
        if nxt:
            parts.append(f"After this topic they usually move on to {nxt}.")
        return " ".join(parts)

    def save(self):
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({
                "topics": self.topics, "genres": self.genres,
                "topic_next": {k: dict(v) for k, v in self.topic_next.items()},
                "mood_next": {k: dict(v) for k, v in self.mood_next.items()}}))
        except Exception:
            pass


_default = None


def default_profile() -> Profile:
    global _default
    if _default is None:
        _default = Profile(PROFILE_PATH)
    return _default
