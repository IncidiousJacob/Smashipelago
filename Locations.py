from BaseClasses import Location
from .Names import (
    CHARACTERS,
    CLASSIC_FIGHTS,
    BONUS_FIGHTS,
    CHARACTER_INTERNAL_IDS,
    CLASSIC_FIGHT_STAGE_IDS,
    DIFFICULTIES,
    DIFFICULTY_VALUE_BY_NAME,
)

BASE_ID = 8801000

class Smash64Location(Location):
    game = "Super Smash Bros. 64"

location_table = {}

_next_id = BASE_ID
for character in CHARACTERS:
    for difficulty in DIFFICULTIES:
        difficulty_value = DIFFICULTY_VALUE_BY_NAME[difficulty]
        for fight in CLASSIC_FIGHTS:
            location_table[f"{character}: {difficulty} Defeat {fight}"] = {
                "code": _next_id,
                "character": character,
                "character_id": CHARACTER_INTERNAL_IDS[character],
                "difficulty": difficulty,
                "difficulty_value": difficulty_value,
                "fight": fight,
                "stage_id": CLASSIC_FIGHT_STAGE_IDS[fight],
                "type": "classic_fight",
            }
            _next_id += 1

    for fight in BONUS_FIGHTS:
        location_table[f"{character}: {fight}"] = {
            "code": _next_id,
            "character": character,
            "character_id": CHARACTER_INTERNAL_IDS[character],
            "fight": fight,
            "type": "bonus_btt",
        }
        _next_id += 1

location_name_to_id = {name: data["code"] for name, data in location_table.items()}

# Runtime lookup: selected player character + RAM stage byte + difficulty byte -> AP location.
location_id_by_character_stage_and_difficulty = {
    (data["character_id"], data["stage_id"], data["difficulty_value"]): data["code"]
    for data in location_table.values()
    if data["type"] == "classic_fight"
}

# Compatibility alias for older imports. Very Easy only.
location_id_by_character_and_stage_id = {
    (data["character_id"], data["stage_id"]): data["code"]
    for data in location_table.values()
    if data["type"] == "classic_fight" and data["difficulty_value"] == 0
}

# Runtime lookup: BTT character byte -> AP location.
location_id_by_btt_character_id = {
    data["character_id"]: data["code"]
    for data in location_table.values()
    if data["type"] == "bonus_btt"
}

master_hand_location_ids = {
    data["code"]
    for data in location_table.values()
    if data["type"] == "classic_fight" and data["fight"] == "Master Hand"
}


master_hand_location_ids_by_difficulty = {
    difficulty_value: {
        data["code"]
        for data in location_table.values()
        if data["type"] == "classic_fight"
        and data["fight"] == "Master Hand"
        and data["difficulty_value"] == difficulty_value
    }
    for difficulty_value in DIFFICULTY_VALUE_BY_NAME.values()
}
