import os
from BaseClasses import Region, Tutorial
import settings
from typing import ClassVar
from worlds.AutoWorld import World, WebWorld

from .Items import Smash64Item, item_table, item_name_to_id
from .Names import CHARACTERS, DIFFICULTY_VALUE_BY_NAME, CLASSIC_FIGHTS, CLASSIC_FIGHT_STAGE_IDS, CHARACTER_INTERNAL_IDS
from .Locations import Smash64Location, location_table, location_name_to_id
from .Options import Smash64Options
from .Rules import set_rules
from .client import Smash64Client
from .rom import Smash64Patch

CHARACTER_OPTION_KEY_BY_NAME = {
    "Mario": "mario",
    "Donkey Kong": "donkey_kong",
    "Link": "link",
    "Samus": "samus",
    "Yoshi": "yoshi",
    "Kirby": "kirby",
    "Fox": "fox",
    "Pikachu": "pikachu",
    "Luigi": "luigi",
    "Captain Falcon": "captain_falcon",
    "Ness": "ness",
    "Jigglypuff": "jigglypuff",
}

CHARACTER_NAME_BY_OPTION_KEY = {
    value: key for key, value in CHARACTER_OPTION_KEY_BY_NAME.items()
}


def normalize_option_key(value) -> str:
    return str(value).lower().replace(" ", "_").replace("-", "_")


def get_enabled_character_names(option_value) -> set[str]:
    names = set()
    for key in option_value:
        normalized = normalize_option_key(key)
        if normalized not in CHARACTER_NAME_BY_OPTION_KEY:
            raise Exception(f"Smash64 option error: unknown character_checks value: {key}")
        names.add(CHARACTER_NAME_BY_OPTION_KEY[normalized])
    return names


DIFFICULTY_OPTION_VALUE_BY_KEY = {
    "very_easy": 0,
    "easy": 1,
    "normal": 2,
    "hard": 3,
    "very_hard": 4,
}


def get_enabled_difficulty_values(option_value) -> set[int]:
    values = set()
    for key in option_value:
        normalized = normalize_option_key(key)
        if normalized not in DIFFICULTY_OPTION_VALUE_BY_KEY:
            raise Exception(f"Smash64 option error: unknown difficulty_checks value: {key}")
        values.add(DIFFICULTY_OPTION_VALUE_BY_KEY[normalized])
    return values


class Smash64Settings(settings.Group):
    class RomFile(settings.UserFilePath):
        description = "Super Smash Bros. 64 USA ROM File (.z64, .n64, or .v64)"
        copy_to = "smash64.z64"
        md5s = Smash64Patch.hashes

    rom_file: RomFile = RomFile(RomFile.copy_to)


class Smash64WebWorld(WebWorld):
    theme = "partyTime"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Super Smash Bros. 64 for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["IncidiousJacob", "ChatGPT"],
    )]


class Smash64World(World):
    """Super Smash Bros. 64 APWorld prototype.

    Checks:
    - Every supported 1P Game / Classic opponent fight as each character.
    - Optional bonus-stage checks for Break the Targets, Board the Platforms, and Race to the Finish.

    Items:
    - Unlock one playable character.
    """

    game = "Super Smash Bros. 64"
    author: str = "IncidiousJacob"
    web = Smash64WebWorld()
    options_dataclass = Smash64Options
    options: Smash64Options

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    topology_present = False

    settings_key = "smash64_settings"
    settings: ClassVar[Smash64Settings]

    def _get_enabled_difficulty_values(self) -> set[int]:
        return get_enabled_difficulty_values(self.options.difficulty_checks.value)

    def _get_enabled_character_names(self) -> set[str]:
        return get_enabled_character_names(self.options.character_checks.value)

    def _choose_starting_character(self, enabled_character_names: set[str]) -> str:
        allowed_characters = [character for character in CHARACTERS if character in enabled_character_names]
        if not allowed_characters:
            raise Exception(
                "Smash64 option error: character_checks must include at least one character."
            )

        if self.options.starting_character.is_random:
            return self.random.choice(allowed_characters)

        selected_character = self.options.starting_character.character_name

        # Archipelago's generic Choice randomization can resolve starting_character
        # to any named character before this world sees it. When character_checks
        # removes that character's locations/items, using that excluded character
        # as the precollected Fighter Pass can make generation fail. Treat an
        # excluded resolved character the same as this world's random-start option:
        # pick only from characters that still have checks in this seed.
        if selected_character not in enabled_character_names:
            return self.random.choice(allowed_characters)

        return selected_character

    def _get_starting_character_name(self) -> str:
        return getattr(self, "selected_starting_character", self.options.starting_character.character_name)

    def _is_randomizing_classic_cpu_characters(self) -> bool:
        return bool(self.options.randomize_classic_cpu_characters.value)

    def _build_classic_cpu_randomizer_table(self) -> dict[str, list[int]]:
        """Build a deterministic per-slot table for the BizHawk client.

        Keys are character_id:stage_id:difficulty_value. Values are three CPU
        character bytes for the three Classic CPU slots found at 0x0A4B8F,
        0x0A4C23, and 0x0A4C97. Master Hand is left out because it is not a
        normal playable-character CPU.
        """
        if not self._is_randomizing_classic_cpu_characters():
            return {}

        enabled_character_names = self._get_enabled_character_names()
        # CPU opponents can safely use the full playable-character roster.
        # character_checks still controls which player characters have AP
        # locations/items; it does not have to restrict who the game loads as CPU.
        cpu_character_ids = [CHARACTER_INTERNAL_IDS[name] for name in CHARACTERS if name in CHARACTER_INTERNAL_IDS]
        if not cpu_character_ids:
            return {}

        table: dict[str, list[int]] = {}
        for character_name in CHARACTERS:
            if character_name not in enabled_character_names:
                continue
            player_char_id = CHARACTER_INTERNAL_IDS[character_name]
            for difficulty_value in sorted(self._get_enabled_difficulty_values()):
                for fight in CLASSIC_FIGHTS:
                    if fight == "Master Hand":
                        continue
                    stage_id = CLASSIC_FIGHT_STAGE_IDS[fight]
                    table[f"{player_char_id}:{stage_id}:{difficulty_value}"] = [
                        self.random.choice(cpu_character_ids),
                        self.random.choice(cpu_character_ids),
                        self.random.choice(cpu_character_ids),
                    ]
        return table

    def generate_early(self):
        include_bonus = bool(self.options.include_bonus_stages.value)
        enabled_difficulty_values = self._get_enabled_difficulty_values()
        enabled_character_names = self._get_enabled_character_names()
        starting_character = self._choose_starting_character(enabled_character_names)
        self.selected_starting_character = starting_character
        self.classic_cpu_randomizer_table = self._build_classic_cpu_randomizer_table()
        goal_difficulty_value = int(self.options.goal_difficulty.value)

        if not enabled_difficulty_values:
            raise Exception(
                "Smash64 option error: difficulty_checks must include at least one difficulty."
            )

        if not enabled_character_names:
            raise Exception(
                "Smash64 option error: character_checks must include at least one character."
            )

        if starting_character not in enabled_character_names:
            raise Exception(
                "Smash64 option error: starting_character must be one of the characters listed in "
                "character_checks, unless starting_character is set to random. Add the starting character "
                "to character_checks, choose a different starting_character, or use random."
            )

        if goal_difficulty_value not in enabled_difficulty_values:
            raise Exception(
                "Smash64 option error: goal_difficulty must be one of the difficulties listed in "
                "difficulty_checks. Add the goal difficulty to difficulty_checks or choose a different "
                "goal_difficulty."
            )

        max_possible_classic_completions = len(enabled_character_names) * len(enabled_difficulty_values)
        required_classic_completions = int(self.options.required_classic_completions.value)
        if required_classic_completions > max_possible_classic_completions:
            raise Exception(
                "Smash64 option error: required_classic_completions is higher than the number "
                "of Master Hand clears that exist with this difficulty_checks setting. "
                f"Requested {required_classic_completions}, but only {max_possible_classic_completions} "
                "are possible. Add more characters to character_checks, add more difficulties to "
                "difficulty_checks, or lower required_classic_completions."
            )

        self.active_locations = {}
        for name, data in location_table.items():
            if data["character"] not in enabled_character_names:
                continue

            if data["type"] in {"bonus_btt", "bonus_btp", "bonus_rttf"} and not include_bonus:
                continue

            if data["type"] == "classic_fight" and self._is_randomizing_classic_cpu_characters():
                continue

            if data["type"] == "classic_fight_randomized_cpu" and not self._is_randomizing_classic_cpu_characters():
                continue

            # Only include Classic fight checks for the exact YAML-selected
            # difficulties. Example: difficulty_checks: [hard] includes only
            # Hard checks and excludes Very Easy/Easy/Normal/Very Hard.
            if data["type"] in {"classic_fight", "classic_fight_randomized_cpu"} and data.get("difficulty_value", 0) not in enabled_difficulty_values:
                continue

            self.active_locations[name] = data

    def create_regions(self):
        menu = Region("Menu", self.player, self.multiworld)
        classic = Region("Classic Mode", self.player, self.multiworld)
        menu.connect(classic, "Start Classic Mode")

        for location_name, data in self.active_locations.items():
            loc = Smash64Location(self.player, location_name, data["code"], classic)
            classic.locations.append(loc)

        self.multiworld.regions += [menu, classic]

    def create_item(self, name: str):
        data = item_table[name]
        return Smash64Item(name, data["classification"], data["code"], self.player)

    def create_items(self):
        starting_character = self._get_starting_character_name()
        starting_item_name = f"{starting_character} Fighter Pass"

        self.multiworld.push_precollected(self.create_item(starting_item_name))

        # Every Master Hand clear is a local progression token for total Classic
        # completions. The first Master Hand clear on goal_difficulty also carries
        # a separate token so the goal can require at least one clear on that difficulty.
        goal_difficulty_value = int(self.options.goal_difficulty.value)
        locked_goal_location_count = 0
        placed_goal_difficulty_clear = False
        for location_name, data in self.active_locations.items():
            if data["type"] not in {"classic_fight", "classic_fight_randomized_cpu"} or data["fight"] != "Master Hand":
                continue

            if int(data.get("difficulty_value", 0)) == goal_difficulty_value and not placed_goal_difficulty_clear:
                self.multiworld.get_location(location_name, self.player).place_locked_item(
                    self.create_item("Goal Difficulty Clear")
                )
                placed_goal_difficulty_clear = True
            else:
                self.multiworld.get_location(location_name, self.player).place_locked_item(
                    self.create_item("Classic Mode Clear")
                )
            locked_goal_location_count += 1

        enabled_character_names = self._get_enabled_character_names()
        character_item_count = 0
        for character in CHARACTERS:
            if character not in enabled_character_names:
                continue
            item_name = f"{character} Fighter Pass"
            if item_name == starting_item_name:
                continue
            self.multiworld.itempool.append(self.create_item(item_name))
            character_item_count += 1

        # Start Classic Mode capped by YAML. The in-game selector stores stocks as:
        # 0 = 1 stock, 1 = 2 stocks, 2 = 3 stocks, 3 = 4 stocks, 4 = 5 stocks.
        # Each Progressive Max Stocks item raises the allowed cap by one until 5.
        starting_max_stocks = int(self.options.starting_max_stocks.value)
        progressive_max_stocks_count = max(0, 5 - starting_max_stocks)
        for _ in range(progressive_max_stocks_count):
            self.multiworld.itempool.append(self.create_item("Progressive Max Stocks"))

        # Difficulty checks can be sparse. Precollect enough Progressive Difficulty
        # items to make the lowest selected difficulty legal from the start, then
        # place enough Progressives to unlock up to the highest selected difficulty.
        # Example: difficulty_checks: [hard] precollects 3 and places 0, so only
        # Hard is selectable and Hard checks are in logic from the start.
        enabled_difficulty_values = self._get_enabled_difficulty_values()
        starting_difficulty_cap = min(enabled_difficulty_values)
        max_selected_difficulty = max(enabled_difficulty_values)

        for _ in range(starting_difficulty_cap):
            self.multiworld.push_precollected(self.create_item("Progressive Difficulty"))

        progressive_difficulty_count = max_selected_difficulty - starting_difficulty_cap
        for _ in range(progressive_difficulty_count):
            self.multiworld.itempool.append(self.create_item("Progressive Difficulty"))

        # Optional progressive damage-dealt system. When enabled, damage output
        # starts at 20% of normal and each Progressive Damage Output item adds
        # another 20%, up to 200% after 9 items. When disabled, the client leaves
        # enemy damage alone and these items are replaced by normal filler.
        progressive_damage_dealt_enabled = bool(self.options.progressive_damage_dealt.value)
        progressive_damage_output_count = 9 if progressive_damage_dealt_enabled else 0
        for _ in range(progressive_damage_output_count):
            self.multiworld.itempool.append(self.create_item("Progressive Damage Output"))

        # Every item placed at a location must have an integer code for the hosted server.
        # Do not create filler with code=None, or uploaded .archipelago files can crash
        # WebHostLib's LocationStore with: TypeError: an integer is required.
        stock_thief_count = int(self.options.stock_thief_count.value)
        heckling_crowd_count = int(self.options.heckling_crowd_count.value)
        trap_count = stock_thief_count + heckling_crowd_count
        filler_count = (
            len(self.active_locations)
            - locked_goal_location_count
            - character_item_count
            - progressive_max_stocks_count
            - progressive_difficulty_count
            - progressive_damage_output_count
            - trap_count
        )
        if filler_count < 0:
            raise Exception(
                "Not enough Smash 64 locations to place the requested trap counts. "
                f"Requested {stock_thief_count} Stock Thief and {heckling_crowd_count} Heckling Crowd traps; "
                f"need {-filler_count} more filler slots. Lower stock_thief_count/heckling_crowd_count "
                "or add more locations."
            )

        for _ in range(stock_thief_count):
            self.multiworld.itempool.append(self.create_item("Stock Thief"))

        for _ in range(heckling_crowd_count):
            self.multiworld.itempool.append(self.create_item("Heckling Crowd"))

        filler_item_names = ["Fans Cheers", "Healing Cheers", "Extra Stock"]
        for _ in range(filler_count):
            self.multiworld.itempool.append(self.create_item(self.random.choice(filler_item_names)))

    def get_filler_item_name(self) -> str:
        return self.random.choice(["Fans Cheers", "Healing Cheers", "Extra Stock", "Heckling Crowd"])

    def generate_output(self, output_directory: str):
        patch = Smash64Patch(player=self.player, player_name=self.player_name)
        out_file_name = self.multiworld.get_out_file_name_base(self.player)
        patch.write(os.path.join(output_directory, f"{out_file_name}{patch.patch_file_ending}"))

    def set_rules(self):
        set_rules(self)

    def fill_slot_data(self):
        return {
            "starting_character": self._get_starting_character_name(),
            "starting_character_randomized": bool(self.options.starting_character.is_random),
            "required_classic_completions": int(self.options.required_classic_completions.value),
            "include_bonus_stages": bool(self.options.include_bonus_stages.value),
            "starting_max_stocks": int(self.options.starting_max_stocks.value),
            "difficulty_checks": sorted(self._get_enabled_difficulty_values()),
            "auto_check_lower_difficulties": bool(self.options.auto_check_lower_difficulties.value),
            "starting_difficulty_cap": min(self._get_enabled_difficulty_values()),
            "max_difficulty_checks": max(self._get_enabled_difficulty_values()),  # compatibility for old clients
            "goal_difficulty": int(self.options.goal_difficulty.value),
            "randomize_classic_cpu_characters": bool(self.options.randomize_classic_cpu_characters.value),
            "classic_cpu_randomizer_table": getattr(self, "classic_cpu_randomizer_table", {}),
            "progressive_damage_dealt": bool(self.options.progressive_damage_dealt.value),
            "starting_damage_dealt_multiplier": 20 if bool(self.options.progressive_damage_dealt.value) else 100,
            "progressive_damage_output_step": 20 if bool(self.options.progressive_damage_dealt.value) else 0,
            "max_damage_dealt_multiplier": 200 if bool(self.options.progressive_damage_dealt.value) else 100,
            "damage_dealt_update_delay": int(self.options.damage_dealt_update_delay.value),
            "heckling_crowd_count": int(self.options.heckling_crowd_count.value),
            "stock_thief_count": int(self.options.stock_thief_count.value),
            "smash_cash": bool(self.options.smash_cash.value),
            "smash_cash_per_fight_win": 10,
            "smash_cash_master_hand_reward": 50,
            "smash_cash_server_tag": "SmashCash",
            "smash_cash_toggle_command": "/Money",
            "smash_cash_stock_cost": 50,
            "smash_cash_heal_costs": {"heal5": 5, "heal10": 10, "heal20": 20, "heal50": 50},
            "death_link": bool(self.options.death_link.value),
            "damage_link": bool(self.options.damage_link.value),
            "energy_link": bool(self.options.energy_link.value),
            "characters": [character for character in CHARACTERS if character in self._get_enabled_character_names()],
        }
