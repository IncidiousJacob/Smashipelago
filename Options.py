from Options import Choice, Range, PerGameCommonOptions, StartInventoryPool, Toggle, OptionSet
from dataclasses import dataclass

class StartingCharacter(Choice):
    """Character available at the start. That character's unlock item is precollected.

    Use random to choose one character from character_checks during generation.
    """
    display_name = "Starting Character"
    option_mario = 0
    option_donkey_kong = 1
    option_link = 2
    option_samus = 3
    option_yoshi = 4
    option_kirby = 5
    option_fox = 6
    option_pikachu = 7
    option_luigi = 8
    option_captain_falcon = 9
    option_ness = 10
    option_jigglypuff = 11
    option_random = 12
    default = 0

    @property
    def character_name(self) -> str:
        return {
            0: "Mario",
            1: "Donkey Kong",
            2: "Link",
            3: "Samus",
            4: "Yoshi",
            5: "Kirby",
            6: "Fox",
            7: "Pikachu",
            8: "Luigi",
            9: "Captain Falcon",
            10: "Ness",
            11: "Jigglypuff",
            12: "Random",
        }[int(self.value)]

    @property
    def is_random(self) -> bool:
        return int(self.value) == 12

class RequiredClassicCompletions(Range):
    """Total Master Hand clears needed to finish. Max possible depends on max_difficulty_checks."""
    display_name = "Required Classic Mode Completions"
    range_start = 1
    range_end = 60
    default = 8

class IncludeBonusStages(Toggle):
    """Whether Break the Targets checks are included."""
    display_name = "Include Bonus Stages"
    default = 1


class StartingMaxStocks(Range):
    """Maximum Classic stock setting available at the start. Progressive Max Stocks items raise this up to 5 stocks."""
    display_name = "Starting Max Stocks"
    range_start = 1
    range_end = 5
    default = 1

class CharacterChecks(OptionSet):
    """Playable characters that have AP locations/items and are allowed by the character lock.

    Example: [mario, luigi] creates locations and Fighter Pass handling only
    for Mario and Luigi. The starting_character must be included here.
    """
    display_name = "Character Checks"
    valid_keys = {
        "mario", "donkey_kong", "link", "samus", "yoshi", "kirby",
        "fox", "pikachu", "luigi", "captain_falcon", "ness", "jigglypuff",
    }
    default = {
        "mario", "donkey_kong", "link", "samus", "yoshi", "kirby",
        "fox", "pikachu", "luigi", "captain_falcon", "ness", "jigglypuff",
    }


class DifficultyChecks(OptionSet):
    """Classic difficulties that have AP checks and are allowed on the difficulty selector.

    Example: [hard] creates only Hard difficulty locations and forces the Classic
    difficulty selector to Hard. Example: [easy, hard] creates only Easy and
    Hard locations; Progressive Difficulty items still unlock the higher allowed
    difficulties according to the normal game values.
    """
    display_name = "Difficulty Checks"
    valid_keys = {"very_easy", "easy", "normal", "hard", "very_hard"}
    default = {"very_easy", "easy", "normal", "hard", "very_hard"}

class AutoCheckLowerDifficulties(Toggle):
    """When enabled, clearing a Classic fight on a difficulty also sends that same character/fight check for lower selected difficulties. Example: Mario clears Easy Defeat Link, so Mario Very Easy Defeat Link is also checked if Very Easy exists in this seed."""
    display_name = "Auto Check Lower Difficulties"
    default = 0


class GoalDifficulty(Choice):
    """Classic difficulty that Master Hand clears must be on to count toward the goal."""
    display_name = "Goal Difficulty"
    option_very_easy = 0
    option_easy = 1
    option_normal = 2
    option_hard = 3
    option_very_hard = 4
    default = 0

    @property
    def difficulty_name(self) -> str:
        return {
            0: "Very Easy",
            1: "Easy",
            2: "Normal",
            3: "Hard",
            4: "Very Hard",
        }[int(self.value)]

class DeathLink(Toggle):
    """When enabled, running out of stocks in a Classic fight sends a DeathLink, and receiving one removes one stock during a Classic fight."""
    display_name = "DeathLink"
    default = 0


class HecklingCrowdCount(Range):
    """Number of Heckling Crowd trap items in the pool."""
    display_name = "Heckling Crowd Count"
    range_start = 1
    range_end = 20
    default = 5

class StockThiefCount(Range):
    """Number of Stock Thief trap items in the pool."""
    display_name = "Stock Thief Count"
    range_start = 1
    range_end = 20
    default = 5


class EnergyLink(Toggle):
    """When enabled, clearing Classic fights deposits EnergyLink and local commands can spend EnergyLink to heal or gain a stock during Classic fights."""
    display_name = "EnergyLink"
    default = 0

class DamageLink(Toggle):
    """When enabled, sends SharedDamage bounce packets every 10 percent damage taken during Classic fights. Received packets add 1 percent damage during a Classic fight."""
    display_name = "DamageLink"
    default = 0

@dataclass
class Smash64Options(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    starting_character: StartingCharacter
    character_checks: CharacterChecks
    required_classic_completions: RequiredClassicCompletions
    include_bonus_stages: IncludeBonusStages
    starting_max_stocks: StartingMaxStocks
    difficulty_checks: DifficultyChecks
    auto_check_lower_difficulties: AutoCheckLowerDifficulties
    goal_difficulty: GoalDifficulty
    heckling_crowd_count: HecklingCrowdCount
    stock_thief_count: StockThiefCount
    death_link: DeathLink
    damage_link: DamageLink
    energy_link: EnergyLink
