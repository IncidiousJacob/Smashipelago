from Options import Choice, Range, PerGameCommonOptions, StartInventoryPool, Toggle
from dataclasses import dataclass

class StartingCharacter(Choice):
    """Character available at the start. That character's unlock item is precollected."""
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
        }[int(self.value)]

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

class MaxDifficultyChecks(Choice):
    """Highest Classic difficulty that has AP checks. Very Easy only includes Very Easy checks; Very Hard includes all difficulty checks."""
    display_name = "Max Difficulty Checks"
    option_very_easy = 0
    option_easy = 1
    option_normal = 2
    option_hard = 3
    option_very_hard = 4
    default = 4

    @property
    def difficulty_name(self) -> str:
        return {
            0: "Very Easy",
            1: "Easy",
            2: "Normal",
            3: "Hard",
            4: "Very Hard",
        }[int(self.value)]

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

@dataclass
class Smash64Options(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    starting_character: StartingCharacter
    required_classic_completions: RequiredClassicCompletions
    include_bonus_stages: IncludeBonusStages
    max_difficulty_checks: MaxDifficultyChecks
    goal_difficulty: GoalDifficulty
    death_link: DeathLink
