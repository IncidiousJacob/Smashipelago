CHARACTERS = [
    "Mario", "Donkey Kong", "Link", "Samus", "Yoshi", "Kirby",
    "Fox", "Pikachu", "Luigi", "Captain Falcon", "Ness", "Jigglypuff",
]

# Playable character values used by SSB64 RAM.
CHARACTER_INTERNAL_IDS = {
    "Mario": 0,
    "Fox": 1,
    "Donkey Kong": 2,
    "Samus": 3,
    "Luigi": 4,
    "Link": 5,
    "Yoshi": 6,
    "Captain Falcon": 7,
    "Kirby": 8,
    "Pikachu": 9,
    "Jigglypuff": 10,
    "Ness": 11,
}

CHARACTER_NAME_BY_INTERNAL_ID = {
    value: name for name, value in CHARACTER_INTERNAL_IDS.items()
}

# 1P Game / Classic checks are named by the opponent/fight, not by the arena.
# The client still uses the stage byte from RAM as the stable signal, then maps
# that stage byte to the fight that takes place there.
CLASSIC_FIGHTS = [
    "Link",
    "Yoshi Team",
    "Fox",
    "Mario Bros.",
    "Pikachu",
    "Giant Donkey Kong",
    "Kirby Team",
    "Samus",
    "Metal Mario",
    "Fighting Polygon Team",
    "Master Hand",
]

# Bonus/checks backed by separate RAM handling.
BONUS_FIGHTS = [
    "Break the Targets",
]

# Values found by ssb64_1p_tracker.lua, remapped from arena -> fight.
# The actual Yoshi Team fight reports stage id 0x0C: Yoshi's Island (no clouds).
CLASSIC_FIGHT_STAGE_IDS = {
    "Mario Bros.": 0x00,          # Peach's Castle
    "Fox": 0x01,                  # Sector Z
    "Giant Donkey Kong": 0x02,    # Congo Jungle
    "Samus": 0x03,                # Planet Zebes
    "Link": 0x04,                 # Hyrule Castle
    "Yoshi Team": 0x0C,           # Yoshi's Island (no clouds)
    "Kirby Team": 0x06,           # Dream Land
    "Pikachu": 0x07,              # Saffron City
    "Metal Mario": 0x0D,          # Meta Crystal
    "Fighting Polygon Team": 0x0E,# Duel Zone
    "Master Hand": 0x10,          # Final Destination
}

CLASSIC_FIGHT_NAME_BY_STAGE_ID = {
    value: name for name, value in CLASSIC_FIGHT_STAGE_IDS.items()
}

# Break the Targets uses a separate character byte during the bonus stage.
# Confirmed by testing:
#   0x0A4B09 = 0x00 for Mario BTT
#   0x0A4B09 = 0x02 for Donkey Kong BTT
#   0x0A4B09 = 0x04 for Luigi BTT
BTT_CHARACTER_ADDR = 0x000A4B09
BTT_STATE_ID = 0x35

# Optional human-readable arena labels for client logs/debug only.
CLASSIC_STAGE_NAME_BY_INTERNAL_ID = {
    0x00: "Peach's Castle",
    0x01: "Sector Z",
    0x02: "Congo Jungle",
    0x03: "Planet Zebes",
    0x04: "Hyrule Castle",
    0x05: "Yoshi's Island",
    0x06: "Dream Land",
    0x07: "Saffron City",
    0x08: "Mushroom Kingdom",
    0x09: "Break the Targets",
    0x0A: "Board the Platforms",
    0x0B: "How to Play",
    0x0C: "Yoshi's Island (no clouds)",
    0x0D: "Meta Crystal",
    0x0E: "Duel Zone",
    0x0F: "Race to the Finish",
    0x10: "Final Destination",
}
