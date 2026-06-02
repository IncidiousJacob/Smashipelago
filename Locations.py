from BaseClasses import Location
from .Names import (
    CHARACTERS,
    CLASSIC_FIGHTS,
    BONUS_FIGHTS,
    CHARACTER_INTERNAL_IDS,
    CLASSIC_FIGHT_STAGE_IDS,
    CLASSIC_FIGHT_GENERIC_NAME_BY_NAME,
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
            stage_id = CLASSIC_FIGHT_STAGE_IDS[fight]
            normal_location_name = f"{character}: {difficulty} Defeat {fight}"
            generic_location_name = f"{character}: {difficulty} {CLASSIC_FIGHT_GENERIC_NAME_BY_NAME[fight]}"
            location_table[normal_location_name] = {
                "code": _next_id,
                "normal_name": normal_location_name,
                "generic_name": generic_location_name,
                "character": character,
                "character_id": CHARACTER_INTERNAL_IDS[character],
                "difficulty": difficulty,
                "difficulty_value": difficulty_value,
                "fight": fight,
                "stage_id": stage_id,
                "type": "classic_fight",
            }
            _next_id += 1

            location_table[generic_location_name] = {
                "code": _next_id,
                "normal_name": normal_location_name,
                "generic_name": generic_location_name,
                "character": character,
                "character_id": CHARACTER_INTERNAL_IDS[character],
                "difficulty": difficulty,
                "difficulty_value": difficulty_value,
                "fight": fight,
                "stage_id": stage_id,
                "type": "classic_fight_randomized_cpu",
            }
            _next_id += 1


    for fight in BONUS_FIGHTS:
        if fight == "Break the Targets":
            bonus_type = "bonus_btt"
        elif fight == "Board the Platforms":
            bonus_type = "bonus_btp"
        elif fight == "Race to the Finish":
            bonus_type = "bonus_rttf"
        else:
            bonus_type = "bonus"

        location_table[f"{character}: {fight}"] = {
            "code": _next_id,
            "character": character,
            "character_id": CHARACTER_INTERNAL_IDS[character],
            "fight": fight,
            "type": bonus_type,
        }
        _next_id += 1

location_name_to_id = {name: data["code"] for name, data in location_table.items()}

# Runtime lookup: selected player character + RAM stage byte + difficulty byte -> AP location.
location_id_by_character_stage_and_difficulty = {
    (data["character_id"], data["stage_id"], data["difficulty_value"]): data["code"]
    for data in location_table.values()
    if data["type"] == "classic_fight"
}

randomized_cpu_location_id_by_character_stage_and_difficulty = {
    (data["character_id"], data["stage_id"], data["difficulty_value"]): data["code"]
    for data in location_table.values()
    if data["type"] == "classic_fight_randomized_cpu"
}

# Compatibility alias for older imports. Very Easy only.
location_id_by_character_and_stage_id = {
    (data["character_id"], data["stage_id"]): data["code"]
    for data in location_table.values()
    if data["type"] == "classic_fight" and data["difficulty_value"] == 0
}

# Runtime lookup: bonus-stage character byte -> AP location.
location_id_by_btt_character_id = {
    data["character_id"]: data["code"]
    for data in location_table.values()
    if data["type"] == "bonus_btt"
}

location_id_by_btp_character_id = {
    data["character_id"]: data["code"]
    for data in location_table.values()
    if data["type"] == "bonus_btp"
}

location_id_by_rttf_character_id = {
    data["character_id"]: data["code"]
    for data in location_table.values()
    if data["type"] == "bonus_rttf"
}

master_hand_location_ids = {
    data["code"]
    for data in location_table.values()
    if data["type"] in {"classic_fight", "classic_fight_randomized_cpu"} and data["fight"] == "Master Hand"
}


master_hand_location_ids_by_difficulty = {
    difficulty_value: {
        data["code"]
        for data in location_table.values()
        if data["type"] in {"classic_fight", "classic_fight_randomized_cpu"}
        and data["fight"] == "Master Hand"
        and data["difficulty_value"] == difficulty_value
    }
    for difficulty_value in DIFFICULTY_VALUE_BY_NAME.values()
}
