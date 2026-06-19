import re
from enum import Enum


class Region(str, Enum):
    CENTER = "center"
    NORTH = "north"
    SOUTH = "south"
    JERUSALEM = "jerusalem"
    REMOTE = "remote"
    UNKNOWN = "unknown"


_CENTER = {
    "tel aviv", "tel aviv-yafo", "tel-aviv", "ramat gan", "givatayim", "herzliya",
    "petah tikva", "petach tikva", "bnei brak", "holon", "bat yam", "rishon lezion",
    "rishon le zion", "raanana", "ra'anana", "kfar saba", "hod hasharon", "netanya",
    "rehovot", "ness ziona", "nes ziona", "yehud", "or yehuda", "airport city",
    "lod", "ramla", "modiin", "modi'in", "petah-tikva",
}
_NORTH = {
    "haifa", "yokneam", "yoqneam", "caesarea", "nazareth", "karmiel", "tiberias",
    "migdal haemek", "kiryat shmona", "akko", "nesher", "tirat carmel", "afula",
}
_SOUTH = {
    "beer sheva", "be'er sheva", "beersheba", "kiryat gat", "ashdod", "ashkelon",
    "eilat", "dimona", "sderot", "yeruham", "ofakim",
}
_JERUSALEM = {"jerusalem", "yerushalayim"}


def classify_location(location: str | None) -> Region:
    if not location:
        return Region.UNKNOWN
    text = location.lower()
    if "remote" in text:
        return Region.REMOTE
    for city in _CENTER:
        if city in text:
            return Region.CENTER
    for city in _JERUSALEM:
        if city in text:
            return Region.JERUSALEM
    for city in _NORTH:
        if city in text:
            return Region.NORTH
    for city in _SOUTH:
        if city in text:
            return Region.SOUTH
    return Region.UNKNOWN


# Non-geographic words in a location string. If, after removing these and "remote",
# nothing remains, the listing is location-agnostic remote (keep). If a place name
# remains, it's pinned to a specific (foreign) place (drop). This allowlist approach
# avoids maintaining an ever-growing country blocklist.
_REMOTE_FILLER = {
    "remote", "hybrid", "onsite", "on", "site", "global", "globally", "worldwide",
    "anywhere", "fully", "partially", "mostly", "optional", "friendly", "first",
    "work", "from", "home", "wfh", "based", "position", "role", "distributed",
    "flexible", "location", "locations", "any", "or", "and", "the", "in", "at",
    "international", "multiple",
}


def _is_location_agnostic_remote(text: str) -> bool:
    """True if no specific place name remains after stripping remote/filler words."""
    tokens = [t for t in re.sub(r"[^a-z]+", " ", text).split() if t not in _REMOTE_FILLER]
    return not tokens


def location_allowed(location: str | None) -> bool:
    if not location:
        return False
    text = location.lower()
    region = classify_location(location)
    if region in (Region.NORTH, Region.SOUTH, Region.JERUSALEM):
        return False
    if region == Region.CENTER:
        return True
    if "israel" in text or "emea" in text or any(city in text for city in _CENTER):
        return True
    if region == Region.REMOTE:
        # Remote is OK only if it's not pinned to a specific (foreign) place.
        return _is_location_agnostic_remote(text)
    # UNKNOWN region, no Israel marker -> drop.
    return False


_REGION_NAME = {
    Region.CENTER: "center", Region.NORTH: "north",
    Region.SOUTH: "south", Region.JERUSALEM: "jerusalem",
}


def region_allowed(location: str | None, districts: set[str], include_remote: bool) -> bool:
    if not location:
        return False
    text = location.lower()
    region = classify_location(location)

    if region == Region.REMOTE:
        return include_remote and _is_location_agnostic_remote(text)

    if region in _REGION_NAME:
        name = _REGION_NAME[region]
        # empty districts = no constraint: keep any Israeli region
        return not districts or name in districts

    # UNKNOWN: keep only if it clearly names Israel / EMEA / a center city
    if "israel" in text or "emea" in text or any(city in text for city in _CENTER):
        return not districts or "center" in districts or "israel" in text
    return False
