"""
classifier_engine.py — Signal classification for the ORRAS system.

Classifies each normalised signal into one of 13 threat/disaster categories,
assigns a track (conflict/disaster/both), and computes a confidence score.
"""

from utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Signal class definitions
# ---------------------------------------------------------------------------

SIGNAL_CLASSES: dict[str, dict] = {
    "armed_conflict": {
        "keywords": [
            "attack", "airstrike", "bombing", "missile", "troops", "battle",
            "clash", "shelling", "artillery", "offensive", "assault", "military",
            "armed", "gunfire", "sniper", "ambush", "combat", "war",
        ],
        "track": "conflict",
        "base_weight": 2.0,
    },
    "troop_movement": {
        "keywords": [
            "deployment", "mobilization", "troops", "convoy", "military exercise",
            "drill", "maneuver", "redeployment", "buildup", "reinforcement",
            "advance", "withdrawal", "retreat", "military movement",
        ],
        "track": "conflict",
        "base_weight": 1.8,
    },
    "political_crisis": {
        "keywords": [
            "coup", "political crisis", "government collapse", "election fraud",
            "impeachment", "resignation", "sanctions", "diplomatic", "protest",
            "opposition", "authoritarian", "crackdown", "political", "regime",
        ],
        "track": "conflict",
        "base_weight": 1.5,
    },
    "civil_unrest": {
        "keywords": [
            "riot", "protest", "unrest", "demonstration", "crowd", "civil unrest",
            "uprising", "insurrection", "strike", "clashes", "violence",
            "looting", "barricade", "tear gas", "crackdown", "suppression",
        ],
        "track": "conflict",
        "base_weight": 1.4,
    },
    "network_disruption": {
        "keywords": [
            "shutdown", "blackout", "internet", "network", "disruption", "outage",
            "connectivity", "censorship", "cyber", "firewall", "block", "cut",
            "offline", "telecom", "communication",
        ],
        "track": "conflict",
        "base_weight": 1.6,
    },
    "earthquake": {
        "keywords": [
            "earthquake", "seismic", "tremor", "magnitude", "richter", "epicenter",
            "aftershock", "fault", "tectonic", "quake", "shaking", "usgs",
        ],
        "track": "disaster",
        "base_weight": 2.0,
    },
    "wildfire": {
        "keywords": [
            "wildfire", "fire", "blaze", "burn", "inferno", "conflagration",
            "firp", "hotspot", "smoke", "flame", "forest fire", "bushfire",
        ],
        "track": "disaster",
        "base_weight": 1.7,
    },
    "flood": {
        "keywords": [
            "flood", "flooding", "inundation", "overflow", "dam break", "tsunami",
            "storm surge", "flash flood", "levee", "submerge", "deluge",
        ],
        "track": "disaster",
        "base_weight": 1.7,
    },
    "hurricane_cyclone": {
        "keywords": [
            "hurricane", "cyclone", "typhoon", "tropical storm", "windspeed",
            "category", "landfall", "eye", "storm", "gale", "tornado", "noaa",
        ],
        "track": "disaster",
        "base_weight": 1.8,
    },
    "disease_outbreak": {
        "keywords": [
            "outbreak", "epidemic", "pandemic", "disease", "virus", "infection",
            "contagion", "ebola", "cholera", "dengue", "mpox", "measles",
            "yellow fever", "cases", "deaths", "mortality", "who", "cfr",
        ],
        "track": "disaster",
        "base_weight": 1.6,
    },
    "humanitarian_crisis": {
        "keywords": [
            "refugee", "displacement", "famine", "starvation", "humanitarian",
            "crisis", "relief", "aid", "shelter", "food insecurity", "malnutrition",
            "civilian", "displaced", "camp", "emergency", "water shortage",
        ],
        "track": "both",
        "base_weight": 1.5,
    },
    "infrastructure_attack": {
        "keywords": [
            "infrastructure", "power plant", "dam", "bridge", "pipeline", "rail",
            "airport", "port", "sabotage", "explosion", "bombing", "power grid",
            "water supply", "communication", "supply chain",
        ],
        "track": "both",
        "base_weight": 1.9,
    },
    "chemical_biological": {
        "keywords": [
            "chemical", "biological", "nerve agent", "sarin", "chlorine gas",
            "anthrax", "bioweapon", "wmd", "weapon of mass destruction",
            "contamination", "toxic", "hazmat", "radiological", "nuclear",
            "radiation", "fallout",
        ],
        "track": "both",
        "base_weight": 2.5,
    },
}


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    """Return list of keywords found in text (case-insensitive)."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]


class ClassifierEngine:
    """
    Classifies normalised signals into threat/disaster categories.

    Each signal receives: signal_class, track, class_confidence, sub_classes.
    """

    def classify_signal(self, signal: dict) -> dict:
        """
        Classify a single signal.

        Searches title + description for keyword matches across all 13 classes.
        The class with the most hits becomes the primary class; others with
        at least one hit become sub_classes.

        Args:
            signal: Normalised signal dict.

        Returns:
            Signal dict updated with: signal_class, track, class_confidence,
            sub_classes.
        """
        text = (
            (signal.get("title") or "")
            + " "
            + (signal.get("description") or "")
            + " "
            + " ".join(signal.get("keywords_matched") or [])
        )

        scores: dict[str, int] = {}
        for cls_name, cls_def in SIGNAL_CLASSES.items():
            hits = _keyword_hits(text, cls_def["keywords"])
            if hits:
                scores[cls_name] = len(hits)

        if not scores:
            signal["signal_class"] = "unclassified"
            signal["track"] = signal.get("track", "unknown")
            signal["class_confidence"] = 0.0
            signal["sub_classes"] = []
            return signal

        # Primary class = highest keyword hit count
        primary = max(scores, key=lambda c: scores[c])
        max_hits = scores[primary]

        # Confidence: fraction of class keywords matched, clamped 0-1
        total_kws = len(SIGNAL_CLASSES[primary]["keywords"])
        confidence = round(min(1.0, max_hits / max(1, total_kws * 0.4)), 2)

        # Sub-classes: any other class with at least 1 hit
        sub_classes = [c for c in scores if c != primary]

        signal["signal_class"] = primary
        signal["track"] = SIGNAL_CLASSES[primary]["track"]
        signal["class_confidence"] = confidence
        signal["sub_classes"] = sub_classes
        return signal

    def classify_all(self, signals: list[dict]) -> list[dict]:
        """
        Classify all signals in the list.

        Args:
            signals: List of normalised signal dicts.

        Returns:
            Updated list with classification fields added to each signal.
        """
        result = [self.classify_signal(s) for s in signals]
        logger.info(f"ClassifierEngine: classified {len(result)} signals.")
        return result

    def get_class_distribution(self, signals: list[dict]) -> dict[str, int]:
        """
        Count signals per class.

        Args:
            signals: List of classified signal dicts.

        Returns:
            Dict of {class_name: count}.
        """
        dist: dict[str, int] = {}
        for sig in signals:
            cls = sig.get("signal_class", "unclassified")
            dist[cls] = dist.get(cls, 0) + 1
        return dist

    def split_by_track(
        self, signals: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """
        Split signals into conflict and disaster lists.

        Hybrid signals (track="both") appear in both lists.

        Args:
            signals: List of classified signal dicts.

        Returns:
            Tuple of (conflict_signals, disaster_signals).
        """
        conflict: list[dict] = []
        disaster: list[dict] = []
        for sig in signals:
            track = sig.get("track", "unknown")
            if track in ("conflict", "both"):
                conflict.append(sig)
            if track in ("disaster", "both"):
                disaster.append(sig)
        return conflict, disaster


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=== classifier_engine.py self-test ===\n")

    sample_signals = [
        {
            "id": "test-001",
            "title": "Missile airstrike hits military troops near Kyiv",
            "description": "Russian armed forces launched a missile attack targeting Ukrainian troop deployments.",
            "keywords_matched": ["missile", "airstrike", "troops"],
            "source": "NewsAPI",
            "track": "unknown",
            "signal_class": "unclassified",
        },
        {
            "id": "test-002",
            "title": "M7.2 Earthquake near Tokyo",
            "description": "USGS detected a magnitude 7.2 seismic tremor near Tokyo coast. Aftershocks expected.",
            "keywords_matched": ["earthquake"],
            "source": "USGS",
            "track": "unknown",
            "signal_class": "unclassified",
        },
        {
            "id": "test-003",
            "title": "Internet shutdown in Iran amid civil unrest and protests",
            "description": "NetBlocks reports a 90% internet blackout in Iran as protesters riot against the regime.",
            "keywords_matched": ["shutdown", "protest", "riot"],
            "source": "NetBlocks",
            "track": "unknown",
            "signal_class": "unclassified",
        },
        {
            "id": "test-004",
            "title": "Ebola outbreak — 200 cases and 120 deaths in DR Congo",
            "description": "WHO reports an active Ebola virus disease outbreak with high case fatality rate.",
            "keywords_matched": ["outbreak", "ebola", "deaths"],
            "source": "WHO",
            "track": "unknown",
            "signal_class": "unclassified",
        },
        {
            "id": "test-005",
            "title": "Pipeline sabotage causes gas explosion, infrastructure attack suspected",
            "description": "A major gas pipeline was destroyed in an explosion. Authorities suspect sabotage.",
            "keywords_matched": ["explosion", "pipeline", "sabotage"],
            "source": "ACLED",
            "track": "unknown",
            "signal_class": "unclassified",
        },
    ]

    engine = ClassifierEngine()
    classified = engine.classify_all(sample_signals)

    for sig in classified:
        print(f"  [{sig['id']}] class={sig['signal_class']}  track={sig['track']}  "
              f"confidence={sig['class_confidence']}  sub_classes={sig['sub_classes']}")

    print()
    dist = engine.get_class_distribution(classified)
    print("Class distribution:", dist)

    conflict, disaster = engine.split_by_track(classified)
    print(f"\nConflict signals: {len(conflict)}")
    print(f"Disaster signals: {len(disaster)}")
