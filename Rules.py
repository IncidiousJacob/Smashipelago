from worlds.generic.Rules import set_rule


DIFFICULTY_ITEM_REQUIREMENTS = {
    0: 0,  # Very Easy
    1: 1,  # Easy
    2: 2,  # Normal
    3: 3,  # Hard
    4: 4,  # Very Hard
}

# Damage output starts at 20% of normal damage. These extra logic gates only
# matter for the YAML-selected first/starting character; all later copies of
# Progressive Damage Output are useful but not required by logic.
FIRST_CHARACTER_DAMAGE_OUTPUT_REQUIREMENTS = {
    "Fox": 2,          # 60% damage output total
    "Kirby Team": 3,   # 80% damage output total
    "Master Hand": 4,  # 100% damage output total
}


def set_rules(world):
    player = world.player
    multiworld = world.multiworld
    starting_character = world._get_starting_character_name()
    progressive_damage_dealt_enabled = bool(world.options.progressive_damage_dealt.value)

    for location_name, data in world.active_locations.items():
        character = data["character"]
        difficulty_value = int(data.get("difficulty_value", 0))
        fight = data.get("fight")
        location_type = data.get("type")
        required_progressive_difficulty = DIFFICULTY_ITEM_REQUIREMENTS.get(difficulty_value, 0)
        required_damage_output = 0

        if progressive_damage_dealt_enabled and location_type in {"classic_fight", "classic_fight_randomized_cpu"} and character == starting_character:
            required_damage_output = FIRST_CHARACTER_DAMAGE_OUTPUT_REQUIREMENTS.get(fight, 0)

        def rule(state, c=character, req=required_progressive_difficulty, dmg_req=required_damage_output):
            if not state.has(f"{c} Fighter Pass", player):
                return False

            if req > 0 and not state.has("Progressive Difficulty", player, req):
                return False

            if dmg_req > 0 and not state.has("Progressive Damage Output", player, dmg_req):
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
