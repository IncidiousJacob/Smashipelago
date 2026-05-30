from BaseClasses import Item, ItemClassification
from .Names import CHARACTERS

BASE_ID = 8800000
FANS_CHEERS_ID = BASE_ID + len(CHARACTERS)
CLASSIC_MODE_CLEAR_ID = BASE_ID + len(CHARACTERS) + 1

class Smash64Item(Item):
    game = "Super Smash Bros. 64"

item_table = {}

for index, character in enumerate(CHARACTERS):
    item_table[f"{character} Fighter Pass"] = {
        "code": BASE_ID + index,
        "classification": ItemClassification.progression,
        "character": character,
    }

item_table["Fans Cheers"] = {
    "code": FANS_CHEERS_ID,
    "classification": ItemClassification.filler,
}

item_table["Classic Mode Clear"] = {
    "code": CLASSIC_MODE_CLEAR_ID,
    "classification": ItemClassification.progression,
}

item_name_to_id = {name: data["code"] for name, data in item_table.items()}
