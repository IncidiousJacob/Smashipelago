from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Set

from NetUtils import ClientStatus
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .Items import BASE_ID as ITEM_BASE_ID
from .Locations import location_id_by_character_and_stage_id, master_hand_location_ids
from .Names import (
    CHARACTERS,
    CHARACTER_INTERNAL_IDS,
    CHARACTER_NAME_BY_INTERNAL_ID,
    CLASSIC_FIGHT_NAME_BY_STAGE_ID,
    CLASSIC_STAGE_NAME_BY_INTERNAL_ID,
    BONUS_STAGE_NAME_BY_STAGE_ID,
)
from .rom import SMASH64_AP_MARKER, SMASH64_AP_MARKER_OFFSET, SMASH64_PLAYER_NAME_OFFSET, SMASH64_PLAYER_NAME_LENGTH

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


ROM_TITLE = b"SMASH BROTHERS      "
UNLOCK_ALL_CHARACTERS_ADDR = 0x0A4938
UNLOCK_ALL_CHARACTERS_VALUE = bytes([0x0F, 0xF0])

# Character-lock addresses.
P1_CHARACTER_SELECT_ADDR = 0x20A8CB
P1_CLASSIC_CHAR_ADDR = 0x000A4B3B

# Classic/1P tracker addresses from ssb64_1p_tracker.lua.
GAME_STATE_ADDR = 0x000A4AD0
CLASSIC_STAGE_ADDR = 0x000A4B19
CLASSIC_CHAR_ADDR = 0x000A4B3B

STATE_IN_BATTLE = 0x01
STATE_RESULTS = 0x33

# Bonus games (Break the Targets / Board the Platforms) do NOT update the normal
# stage byte (CLASSIC_STAGE_ADDR reads 0x00 during a bonus game) and do not pass
# through STATE_IN_BATTLE. Instead GAME_STATE_ADDR reads 0x35 while in a bonus
# game (RA: "in BTB or BTF bonus game"). Confirmed from live RAM dumps.
STATE_IN_BONUS = 0x35

# There is no reliable RAM byte that distinguishes Break the Targets from Board
# the Platforms at read time (every candidate byte read identically or tracked
# unrelated ladder progress). Instead we use the FIXED 1P Classic ladder order,
# which is identical for every character:
#   ... -> Fox fight -> [Break the Targets] -> ... -> Giant DK fight -> [Board the Platforms] -> ...
# So the bonus game's identity is determined by which fight was cleared most
# recently before entering the bonus state. We anchor on the fight STAGE id.
BONUS_AFTER_FIGHT_STAGE = {
    0x01: 0x09,  # after Fox (Sector Z)      -> Break the Targets
    0x02: 0x0A,  # after Giant DK (Congo)    -> Board the Platforms
}

CHARACTER_SELECT_VALUE_BY_NAME = {
    name: CHARACTER_INTERNAL_IDS[name]
    for name in CHARACTER_INTERNAL_IDS
}

CHARACTER_NAME_BY_SELECT_VALUE = CHARACTER_NAME_BY_INTERNAL_ID

CHARACTER_BY_ITEM_ID: Dict[int, str] = {
    ITEM_BASE_ID + index: character for index, character in enumerate(CHARACTERS)
}


class Smash64Client(BizHawkClient):
    game = "Super Smash Bros. 64"
    system = "N64"
    patch_suffix = ".apsmash64"

    local_checked_locations: Set[int]
    player_name: str | None
    last_locked_character_value: int | None
    last_classic_locked_character_value: int | None
    last_unlocked_character_names: Set[str]
    last_seen_game_state: int | None
    prev_game_state: int | None
    snapshot_stage: int | None
    snapshot_char: int | None
    last_fight_stage: int | None
    last_fight_char: int | None
    goal_sent: bool

    def __init__(self) -> None:
        super().__init__()
        self.local_checked_locations = set()
        self.player_name = None
        self.last_locked_character_value = None
        self.last_classic_locked_character_value = None
        self.last_unlocked_character_names = set()
        self.last_seen_game_state = None
        self.prev_game_state = None
        self.snapshot_stage = None
        self.snapshot_char = None
        self.last_fight_stage = None
        self.last_fight_char = None
        self.goal_sent = False

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        from CommonClient import logger

        try:
            rom_title, ap_marker = await bizhawk.read(ctx.bizhawk_ctx, [
                (0x20, 0x14, "ROM"),
                (SMASH64_AP_MARKER_OFFSET, len(SMASH64_AP_MARKER), "ROM"),
            ])
        except bizhawk.RequestFailedError:
            return False

        if rom_title != ROM_TITLE:
            return False

        if ap_marker == b"\xFF" * len(SMASH64_AP_MARKER):
            logger.info("ERROR: You appear to be running an unpatched Super Smash Bros. 64 ROM. "
                        "Generate a .apsmash64 patch, open it with ArchipelagoLauncher, and load the patched .z64 in BizHawk.")
            return False

        if ap_marker != SMASH64_AP_MARKER:
            logger.info("ERROR: This Super Smash Bros. 64 ROM was patched with an incompatible Smash64 APWorld/client version.")
            return False

        try:
            player_name_raw = (await bizhawk.read(ctx.bizhawk_ctx, [
                (SMASH64_PLAYER_NAME_OFFSET, SMASH64_PLAYER_NAME_LENGTH, "ROM"),
            ]))[0]
            self.player_name = player_name_raw.split(b"\0", 1)[0].decode("utf-8")
        except (UnicodeDecodeError, bizhawk.RequestFailedError):
            self.player_name = None

        ctx.game = self.game
        # 0b111 = full item handling: remote items + the player's own local item
        # finds + starting inventory. Fighter Passes are usually found in the
        # player's own world, so 0b001 (remote only) meant a found pass never
        # arrived in items_received and the character stayed locked.
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.016

        self.last_locked_character_value = None
        self.last_classic_locked_character_value = None
        self.last_unlocked_character_names = set()
        self.last_seen_game_state = None
        self.prev_game_state = None
        self.snapshot_stage = None
        self.snapshot_char = None
        self.last_fight_stage = None
        self.last_fight_char = None
        self.goal_sent = False
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        if self.player_name:
            ctx.auth = self.player_name

    def get_unlocked_character_names(self, ctx: "BizHawkClientContext") -> Set[str]:
        unlocked: Set[str] = set()

        slot_data = getattr(ctx, "slot_data", None) or {}
        starting_character = slot_data.get("starting_character", "Mario")
        if starting_character in CHARACTER_SELECT_VALUE_BY_NAME:
            unlocked.add(starting_character)

        for network_item in getattr(ctx, "items_received", []):
            character = CHARACTER_BY_ITEM_ID.get(network_item.item)
            if character is not None:
                unlocked.add(character)

        if not unlocked:
            unlocked.add("Mario")

        return unlocked

    async def _burst_write_u8(self, ctx: "BizHawkClientContext", address: int, value: int, repeats: int = 12) -> int:
        packet = (address, bytes([value & 0xFF]), "RDRAM")
        for _ in range(repeats):
            await bizhawk.write(ctx.bizhawk_ctx, [packet])
        return (await bizhawk.read(ctx.bizhawk_ctx, [(address, 1, "RDRAM")]))[0][0]

    async def _clamp_character_byte(
        self,
        ctx: "BizHawkClientContext",
        address: int,
        fallback_value: int,
        unlocked_values: Set[int],
    ) -> int | None:
        current_value = (await bizhawk.read(ctx.bizhawk_ctx, [
            (address, 1, "RDRAM"),
        ]))[0][0]

        if current_value in CHARACTER_NAME_BY_SELECT_VALUE and current_value not in unlocked_values:
            await self._burst_write_u8(ctx, address, fallback_value)
            return current_value

        return None

    async def enforce_character_locks(self, ctx: "BizHawkClientContext") -> None:
        unlocked_names = self.get_unlocked_character_names(ctx)
        unlocked_values = {
            CHARACTER_SELECT_VALUE_BY_NAME[name]
            for name in unlocked_names
            if name in CHARACTER_SELECT_VALUE_BY_NAME
        }
        if not unlocked_values:
            return

        slot_data = getattr(ctx, "slot_data", None) or {}
        starting_character = slot_data.get("starting_character", "Mario")
        fallback_value = CHARACTER_SELECT_VALUE_BY_NAME.get(starting_character)
        if fallback_value not in unlocked_values:
            fallback_value = min(unlocked_values)
        fallback_name = CHARACTER_NAME_BY_SELECT_VALUE[fallback_value]

        self.last_unlocked_character_names = set(unlocked_names)

        locked_css = await self._clamp_character_byte(
            ctx,
            P1_CHARACTER_SELECT_ADDR,
            fallback_value,
            unlocked_values,
        )
        self.last_locked_character_value = locked_css

        locked_classic = await self._clamp_character_byte(
            ctx,
            P1_CLASSIC_CHAR_ADDR,
            fallback_value,
            unlocked_values,
        )
        self.last_classic_locked_character_value = locked_classic

    async def handle_classic_stage_checks(self, ctx: "BizHawkClientContext") -> None:
        game_state, stage_id, char_id = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (CLASSIC_STAGE_ADDR, 1, "RDRAM"),
            (CLASSIC_CHAR_ADDR, 1, "RDRAM"),
        ])]

        self.last_seen_game_state = game_state

        # Snapshot the stage/character on the rising edge into a battle. This is
        # the logic that reliably detects fight clears; do not re-latch on other
        # frames, or a stale stage byte from a previous fight can pollute the
        # snapshot and cause the wrong (or a repeated) location to be sent.
        if game_state == STATE_IN_BATTLE and self.prev_game_state != STATE_IN_BATTLE:
            self.snapshot_stage = stage_id
            self.snapshot_char = char_id

        # Bonus games never set STATE_IN_BATTLE and never update the normal stage
        # byte. On the rising edge into the bonus state (0x35), resolve which bonus
        # game this is from the LAST FIGHT cleared, using the fixed ladder order:
        # Break the Targets always follows the Fox fight; Board the Platforms always
        # follows the Giant DK fight. There is no reliable in-RAM byte that names the
        # bonus game, so this ladder-position approach is what we anchor on.
        if game_state == STATE_IN_BONUS and self.prev_game_state != STATE_IN_BONUS:
            from CommonClient import logger

            mapped_stage = None
            if self.last_fight_stage is not None:
                mapped_stage = BONUS_AFTER_FIGHT_STAGE.get(self.last_fight_stage)

            bonus_label = BONUS_STAGE_NAME_BY_STAGE_ID.get(mapped_stage) if mapped_stage is not None else None
            logger.info(
                f"[smash64] entered bonus game: char=0x{char_id:02X} "
                f"last_fight_stage="
                f"{'0x%02X' % self.last_fight_stage if self.last_fight_stage is not None else None} "
                f"-> {bonus_label or 'unresolved'}"
            )

            if mapped_stage is not None:
                # Use the character from the last fight (char byte may read 0x00 or
                # a sentinel during the bonus game itself).
                self.snapshot_stage = mapped_stage
                self.snapshot_char = (
                    self.last_fight_char
                    if self.last_fight_char is not None
                    else char_id
                )
                # Consume the anchor so the same fight can't resolve two bonuses.
                self.last_fight_stage = None

        if game_state == STATE_RESULTS and self.prev_game_state != STATE_RESULTS:
            if self.snapshot_stage is not None and self.snapshot_char is not None:
                from CommonClient import logger

                location_id = location_id_by_character_and_stage_id.get((self.snapshot_char, self.snapshot_stage))
                stage_name = CLASSIC_STAGE_NAME_BY_INTERNAL_ID.get(self.snapshot_stage, f"Unknown Stage 0x{self.snapshot_stage:02X}")
                fight_name = CLASSIC_FIGHT_NAME_BY_STAGE_ID.get(self.snapshot_stage)
                bonus_name = BONUS_STAGE_NAME_BY_STAGE_ID.get(self.snapshot_stage)
                char_name = CHARACTER_NAME_BY_SELECT_VALUE.get(self.snapshot_char, f"Unknown 0x{self.snapshot_char:02X}")
                kind = "bonus" if bonus_name is not None else ("fight" if fight_name is not None else "unmapped")

                # Surfaces what RAM reported on stage clear (char, stage byte,
                # resolved kind/location) so detection can be traced without a
                # hex editor.
                logger.debug(
                    f"[smash64] cleared: char={char_name}(0x{self.snapshot_char:02X}) "
                    f"stage=0x{self.snapshot_stage:02X}({stage_name}) kind={kind} "
                    f"loc_id={location_id}"
                )

                if location_id is not None:
                    already_checked = set(getattr(ctx, "checked_locations", set()))
                    already_checked.update(getattr(ctx, "locations_checked", set()))
                    if location_id not in self.local_checked_locations and location_id not in already_checked:
                        self.local_checked_locations.add(location_id)
                        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": [location_id]}])
                else:
                    logger.debug(
                        f"[smash64] no AP location for (char 0x{self.snapshot_char:02X}, "
                        f"stage 0x{self.snapshot_stage:02X}) - either not a check or bonus stages disabled"
                    )

                # Remember the last FIGHT cleared so the next bonus game can be
                # identified by ladder position. Only fights update this; bonus
                # clears must not, or two bonuses in a row would mis-resolve.
                if kind == "fight":
                    self.last_fight_stage = self.snapshot_stage
                    self.last_fight_char = self.snapshot_char
            else:
                pass

            self.snapshot_stage = None
            self.snapshot_char = None

        self.prev_game_state = game_state

        await self.check_goal(ctx)

    async def check_goal(self, ctx: "BizHawkClientContext") -> None:
        if self.goal_sent:
            return

        slot_data = getattr(ctx, "slot_data", None) or {}
        required = int(slot_data.get("required_classic_completions", 8))

        checked = set(getattr(ctx, "checked_locations", set()))
        checked.update(getattr(ctx, "locations_checked", set()))
        checked.update(self.local_checked_locations)

        master_hand_clears = len(master_hand_location_ids.intersection(checked))
        if master_hand_clears >= required:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            self.goal_sent = True

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        try:
            # Keep all characters visible in the base game so AP can control access.
            await bizhawk.write(ctx.bizhawk_ctx, [
                (UNLOCK_ALL_CHARACTERS_ADDR, UNLOCK_ALL_CHARACTERS_VALUE, "RDRAM"),
            ])

            await self.handle_classic_stage_checks(ctx)
            await self.enforce_character_locks(ctx)
        except bizhawk.RequestFailedError:
            pass
