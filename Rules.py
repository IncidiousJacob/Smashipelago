from worlds.generic.Rules import set_rule


def set_rules(world):
    player = world.player
    multiworld = world.multiworld

    # Iterate only the locations this slot actually created (active_locations),
    # not the full location_table. The full table includes bonus-stage locations
    # that are absent when include_bonus_stages is off; calling get_location on a
    # location that was never created raises KeyError.
    for location_name, data in world.active_locations.items():
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
