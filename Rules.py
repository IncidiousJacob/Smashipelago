from worlds.generic.Rules import set_rule


DIFFICULTY_ITEM_REQUIREMENTS = {
    0: 0,  # Very Easy
    1: 1,  # Easy
    2: 2,  # Normal
    3: 3,  # Hard
    4: 4,  # Very Hard
}


def set_rules(world):
    player = world.player
    multiworld = world.multiworld

    for location_name, data in world.active_locations.items():
        character = data["character"]
        difficulty_value = int(data.get("difficulty_value", 0))
        required_progressive_difficulty = DIFFICULTY_ITEM_REQUIREMENTS.get(difficulty_value, 0)

        def rule(state, c=character, req=required_progressive_difficulty):
            if not state.has(f"{c} Fighter Pass", player):
                return False

            if req > 0 and not state.has("Progressive Difficulty", player, req):
                return False

            return True

        set_rule(multiworld.get_location(location_name, player), rule)

    required = int(world.options.required_classic_completions.value)

    # Goal requires the requested number of total Master Hand clears, plus at
    # least one Master Hand clear on the YAML-selected goal_difficulty. One goal
    # difficulty location contains "Goal Difficulty Clear" instead of a normal
    # clear token, so it also counts toward the total.
    multiworld.completion_condition[player] = lambda state: (
        state.count("Classic Mode Clear", player) + state.count("Goal Difficulty Clear", player) >= required
        and state.has("Goal Difficulty Clear", player)
    )
