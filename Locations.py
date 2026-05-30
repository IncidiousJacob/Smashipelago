from BaseClasses import Location
from .Names import (
    CHARACTERS,
    CLASSIC_FIGHTS,
    CHARACTER_INTERNAL_IDS,
    CLASSIC_FIGHT_STAGE_IDS,
    BONUS_STAGES,
    BONUS_STAGE_IDS,
)

BASE_ID = 8801000
# Bonus locations get their own id block above the fight block so that adding
# or removing fights never shifts a bonus id (which would break existing seeds).
BONUS_BASE_ID = 8801500

class Smash64Location(Location):
    game = "Super Smash Bros. 64"

location_table = {}

_next_id = BASE_ID
for character in CHARACTERS:
    for fight in CLASSIC_FIGHTS:
        location_table[f"{character}: Defeat {fight}"] = {
            "code": _next_id,
            "character": character,
            "character_id": CHARACTER_INTERNAL_IDS[character],
            "fight": fight,
            "stage_id": CLASSIC_FIGHT_STAGE_IDS[fight],
            "type": "classic_fight",
        }
        _next_id += 1

# Bonus stage locations. These always exist in the table (AP needs every id
# registered up front); whether they are actually created for a slot is
# controlled by the include_bonus_stages option in __init__.
_next_bonus_id = BONUS_BASE_ID
for character in CHARACTERS:
    for bonus in BONUS_STAGES:
        location_table[f"{character}: Clear {bonus}"] = {
            "code": _next_bonus_id,
            "character": character,
            "character_id": CHARACTER_INTERNAL_IDS[character],
            "fight": bonus,
            "stage_id": BONUS_STAGE_IDS[bonus],
            "type": "bonus_stage",
        }
        _next_bonus_id += 1

location_name_to_id = {name: data["code"] for name, data in location_table.items()}

# Runtime lookup: selected player character + RAM stage byte -> AP location.
# This includes both fights and bonus stages; the client looks up whatever the
# stage byte reports, so a bonus location only ever resolves if its slot created
# it (uncreated locations are simply absent from the multiworld).
location_id_by_character_and_stage_id = {
    (data["character_id"], data["stage_id"]): data["code"]
    for data in location_table.values()
}

master_hand_location_ids = {
    data["code"]
    for data in location_table.values()
    if data["fight"] == "Master Hand"
}

bonus_stage_location_names = {
    name
    for name, data in location_table.items()
    if data["type"] == "bonus_stage"
}
