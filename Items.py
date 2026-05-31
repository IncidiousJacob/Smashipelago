from BaseClasses import Item, ItemClassification
from .Names import CHARACTERS

BASE_ID = 8800000
FANS_CHEERS_ID = BASE_ID + len(CHARACTERS)
CLASSIC_MODE_CLEAR_ID = BASE_ID + len(CHARACTERS) + 1
HEALING_CHEERS_ID = BASE_ID + len(CHARACTERS) + 2
HECKLING_CROWD_ID = BASE_ID + len(CHARACTERS) + 3
PROGRESSIVE_MAX_STOCKS_ID = BASE_ID + len(CHARACTERS) + 4
EXTRA_STOCK_ID = BASE_ID + len(CHARACTERS) + 5
STOCK_THIEF_ID = BASE_ID + len(CHARACTERS) + 6
PROGRESSIVE_DIFFICULTY_ID = BASE_ID + len(CHARACTERS) + 7
GOAL_DIFFICULTY_CLEAR_ID = BASE_ID + len(CHARACTERS) + 8

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

item_table["Healing Cheers"] = {
    "code": HEALING_CHEERS_ID,
    "classification": ItemClassification.filler,
}

item_table["Heckling Crowd"] = {
    "code": HECKLING_CROWD_ID,
    "classification": ItemClassification.trap,
}

item_table["Progressive Max Stocks"] = {
    "code": PROGRESSIVE_MAX_STOCKS_ID,
    "classification": ItemClassification.progression,
}

item_table["Extra Stock"] = {
    "code": EXTRA_STOCK_ID,
    "classification": ItemClassification.filler,
}

item_table["Stock Thief"] = {
    "code": STOCK_THIEF_ID,
    "classification": ItemClassification.trap,
}

item_table["Progressive Difficulty"] = {
    "code": PROGRESSIVE_DIFFICULTY_ID,
    "classification": ItemClassification.progression,
}

item_table["Goal Difficulty Clear"] = {
    "code": GOAL_DIFFICULTY_CLEAR_ID,
    "classification": ItemClassification.progression,
}

# Rebuild after all items are added.
item_name_to_id = {name: data["code"] for name, data in item_table.items()}
