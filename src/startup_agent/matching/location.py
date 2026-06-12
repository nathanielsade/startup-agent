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


def location_allowed(location: str | None) -> bool:
    if not location:
        return False
    region = classify_location(location)
    if region in (Region.REMOTE, Region.CENTER):
        return True
    if region in (Region.NORTH, Region.SOUTH, Region.JERUSALEM):
        return False
    # UNKNOWN region: keep only if the string clearly says Israel (unlisted Israeli city)
    return "israel" in location.lower()
