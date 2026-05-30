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
        ctx.items_handling = 0b001
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.016

        self.last_locked_character_value = None
        self.last_classic_locked_character_value = None
        self.last_unlocked_character_names = set()
        self.last_seen_game_state = None
        self.prev_game_state = None
        self.snapshot_stage = None
        self.snapshot_char = None
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

        if game_state == STATE_IN_BATTLE and self.prev_game_state != STATE_IN_BATTLE:
            self.snapshot_stage = stage_id
            self.snapshot_char = char_id

        if game_state == STATE_RESULTS and self.prev_game_state != STATE_RESULTS:
            if self.snapshot_stage is not None and self.snapshot_char is not None:
                location_id = location_id_by_character_and_stage_id.get((self.snapshot_char, self.snapshot_stage))
                stage_name = CLASSIC_STAGE_NAME_BY_INTERNAL_ID.get(self.snapshot_stage, f"Unknown Stage 0x{self.snapshot_stage:02X}")
                fight_name = CLASSIC_FIGHT_NAME_BY_STAGE_ID.get(self.snapshot_stage, f"Unsupported Stage 0x{self.snapshot_stage:02X}")
                char_name = CHARACTER_NAME_BY_SELECT_VALUE.get(self.snapshot_char, f"Unknown 0x{self.snapshot_char:02X}")

                if location_id is not None:
                    already_checked = set(getattr(ctx, "checked_locations", set()))
                    already_checked.update(getattr(ctx, "locations_checked", set()))
                    if location_id not in self.local_checked_locations and location_id not in already_checked:
                        self.local_checked_locations.add(location_id)
                        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": [location_id]}])
                    else:
                        pass
                else:
                    pass
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
