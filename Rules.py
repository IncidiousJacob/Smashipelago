from worlds.generic.Rules import set_rule
from .Locations import location_table


def set_rules(world):
    player = world.player
    multiworld = world.multiworld

    for location_name, data in location_table.items():
        character = data["character"]
        set_rule(
            multiworld.get_location(location_name, player),
            lambda state, c=character: state.has(f"{c} Fighter Pass", player),
        )

    required = int(world.options.required_classic_completions.value)

    # Every character's Master Hand location contains a locked
    # "Classic Mode Clear" progression item. The YAML option controls how
    # many of those clears must be collected before the slot is considered done.
    multiworld.completion_condition[player] = lambda state: state.has(
        "Classic Mode Clear", player, required
    )
