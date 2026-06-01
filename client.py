from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Set
import time
import Utils

from NetUtils import ClientStatus
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .Items import BASE_ID as ITEM_BASE_ID, HEALING_CHEERS_ID, HECKLING_CROWD_ID, PROGRESSIVE_MAX_STOCKS_ID, EXTRA_STOCK_ID, STOCK_THIEF_ID, PROGRESSIVE_DIFFICULTY_ID
from .Locations import location_id_by_character_stage_and_difficulty, location_id_by_btt_character_id, master_hand_location_ids, master_hand_location_ids_by_difficulty
from .Names import (
    CHARACTERS,
    CHARACTER_INTERNAL_IDS,
    CHARACTER_NAME_BY_INTERNAL_ID,
    CLASSIC_FIGHT_NAME_BY_STAGE_ID,
    CLASSIC_STAGE_NAME_BY_INTERNAL_ID,
    DIFFICULTY_NAME_BY_VALUE,
    BTT_CHARACTER_ADDR,
    BTT_STATE_ID,
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
BTT_CHAR_ADDR = BTT_CHARACTER_ADDR
P1_HEALTH_ADDR = 0x0026805E
P1_HEALTH_SYSTEM_BUS_ADDR = 0x8026805E
P1_STOCKS_ADDR = 0x000A4B43
MAX_STOCKS_SELECT_ADDR = 0x00138FBB
DIFFICULTY_SELECT_ADDR = 0x00138FB7

ENERGY_LINK_KEY = "EnergyLink"
ENERGY_LINK_FIGHT_DEPOSIT = 10
ENERGY_LINK_CLASSIC_CLEAR_DEPOSIT = 50
ENERGY_LINK_HEAL_5_COST = 5
ENERGY_LINK_HEAL_10_COST = 10
ENERGY_LINK_HEAL_20_COST = 20
ENERGY_LINK_HEAL_50_COST = 50
ENERGY_LINK_STOCK_COST = 50

DAMAGE_LINK_SEND_COOLDOWN_SECONDS = 10.0
DAMAGE_LINK_AFTER_CHECK_BLOCK_SECONDS = 30.0
DAMAGE_LINK_FIGHT_START_GRACE_SECONDS = 3.0


def _energy_link_key(ctx: "BizHawkClientContext") -> str:
    """Use Archipelago's standard shared EnergyLink storage key.

    Factorio and the common client use the plain key "EnergyLink".
    The previous Smash64 builds used a team-scoped key like "EnergyLink0",
    which isolated Smash64 from the real shared pool and prevented it from
    seeing EnergyLink sent by other games.
    """
    return ENERGY_LINK_KEY


STATE_IN_BATTLE = 0x01
STATE_LOADING = 0x0E
STATE_RESULTS = 0x33
STATE_BTT = BTT_STATE_ID

CHARACTER_SELECT_VALUE_BY_NAME = {
    name: CHARACTER_INTERNAL_IDS[name]
    for name in CHARACTER_INTERNAL_IDS
}

CHARACTER_NAME_BY_SELECT_VALUE = CHARACTER_NAME_BY_INTERNAL_ID

CHARACTER_BY_ITEM_ID: Dict[int, str] = {
    ITEM_BASE_ID + index: character for index, character in enumerate(CHARACTERS)
}



def cmd_smash64_characters(self) -> None:
    """List unlocked and locked Super Smash Bros. 64 characters."""
    from CommonClient import logger

    handler = getattr(self.ctx, "client_handler", None)
    if handler is None or not hasattr(handler, "get_unlocked_character_names"):
        logger.info("Smash64 client is not active yet. Load the patched ROM first.")
        return

    enabled_names = handler.get_enabled_character_names(self.ctx)
    unlocked_names = handler.get_unlocked_character_names(self.ctx)
    unlocked = [name for name in CHARACTERS if name in enabled_names and name in unlocked_names]
    locked = [name for name in CHARACTERS if name in enabled_names and name not in unlocked_names]

    logger.info(f"Unlocked characters ({len(unlocked)}/{len(enabled_names)}): "
                f"{', '.join(unlocked) if unlocked else 'none'}")
    logger.info(f"Locked characters: {', '.join(locked) if locked else 'none'}")
    disabled = [name for name in CHARACTERS if name not in enabled_names]
    if disabled:
        logger.info(f"Disabled by YAML: {', '.join(disabled)}")

    fallback_value = handler._get_character_fallback_value(self.ctx)
    if fallback_value in CHARACTER_NAME_BY_SELECT_VALUE:
        logger.info(f"Current fallback character: {CHARACTER_NAME_BY_SELECT_VALUE[fallback_value]}")


def cmd_smash64_deathlink(self) -> None:
    """Toggle DeathLink on/off for this client session."""
    from CommonClient import logger

    handler = getattr(self.ctx, "client_handler", None)
    if handler is None or not hasattr(handler, "death_link_user_enabled"):
        logger.info("Smash64 client is not active yet. Load the patched ROM first.")
        return

    slot_data = getattr(self.ctx, "slot_data", None) or {}
    if not bool(slot_data.get("death_link", False)):
        logger.info("DeathLink is disabled in this seed. Set death_link: true in the YAML to allow toggling.")
        return

    handler.death_link_user_enabled = not bool(handler.death_link_user_enabled)
    handler.death_link_status_sent = False
    if not handler.death_link_user_enabled:
        handler.pending_deathlinks = 0
        handler.sent_deathlink_for_current_stockout = False

    logger.info(f"DeathLink {'ON' if handler.death_link_user_enabled else 'OFF'}")


def cmd_smash64_goal(self) -> None:
    """Show Classic Mode goal progress."""
    from CommonClient import logger

    handler = getattr(self.ctx, "client_handler", None)
    if handler is None or not hasattr(handler, "local_checked_locations"):
        logger.info("Smash64 client is not active yet. Load the patched ROM first.")
        return

    slot_data = getattr(self.ctx, "slot_data", None) or {}
    required = int(slot_data.get("required_classic_completions", 8) or 8)
    goal_difficulty = int(slot_data.get("goal_difficulty", 0) or 0)
    goal_difficulty_name = DIFFICULTY_NAME_BY_VALUE.get(goal_difficulty, f"Unknown {goal_difficulty}")

    checked = set(getattr(self.ctx, "checked_locations", set()) or set())
    checked.update(getattr(self.ctx, "locations_checked", set()) or set())
    checked.update(getattr(handler, "local_checked_locations", set()) or set())

    total_master_hand_clears = len(master_hand_location_ids.intersection(checked))
    goal_master_hand_ids = master_hand_location_ids_by_difficulty.get(goal_difficulty, set())
    goal_difficulty_clears = len(goal_master_hand_ids.intersection(checked))
    has_goal_difficulty_clear = goal_difficulty_clears > 0

    logger.info(
        f"Classic Mode clears: {total_master_hand_clears}/{required} "
        f"({'complete' if total_master_hand_clears >= required else 'incomplete'})"
    )
    logger.info(
        f"Goal difficulty clear ({goal_difficulty_name}): "
        f"{'yes' if has_goal_difficulty_clear else 'no'} "
        f"({goal_difficulty_clears} clear{'s' if goal_difficulty_clears != 1 else ''})"
    )

    if total_master_hand_clears >= required and has_goal_difficulty_clear:
        logger.info("Goal requirement met.")
    else:
        remaining = max(0, required - total_master_hand_clears)
        if remaining > 0:
            logger.info(f"Need {remaining} more Classic Mode clear{'s' if remaining != 1 else ''}.")
        if not has_goal_difficulty_clear:
            logger.info(f"Need at least one Master Hand clear on {goal_difficulty_name}.")


def _smash64_energylink_handler(ctx: "BizHawkClientContext"):
    handler = getattr(ctx, "client_handler", None)
    if handler is None or not hasattr(handler, "queue_energy_link_withdraw"):
        return None
    return handler


def cmd_smash64_energylink(self) -> None:
    """Show EnergyLink balance and withdraw commands."""
    from CommonClient import logger

    handler = _smash64_energylink_handler(self.ctx)
    if handler is None:
        logger.info("Smash64 client is not active yet. Load the patched ROM first.")
        return

    slot_data = getattr(self.ctx, "slot_data", None) or {}
    if not bool(slot_data.get("energy_link", False)):
        logger.info("EnergyLink is disabled in this seed. Set energy_link: true in the YAML.")
        return

    logger.info(f"EnergyLink balance: {handler.energy_link_value}")
    logger.info("Withdraw commands: /el_heal5, /el_heal10, /el_heal20, /el_heal50, /el_stock")


def cmd_smash64_el_heal5(self) -> None:
    """Spend 5 EnergyLink to heal 5%."""
    handler = _smash64_energylink_handler(self.ctx)
    if handler is not None:
        handler.queue_energy_link_withdraw(self.ctx, "heal", 5, ENERGY_LINK_HEAL_5_COST)


def cmd_smash64_el_heal10(self) -> None:
    """Spend 10 EnergyLink to heal 10%."""
    handler = _smash64_energylink_handler(self.ctx)
    if handler is not None:
        handler.queue_energy_link_withdraw(self.ctx, "heal", 10, ENERGY_LINK_HEAL_10_COST)


def cmd_smash64_el_heal20(self) -> None:
    """Spend 20 EnergyLink to heal 20%."""
    handler = _smash64_energylink_handler(self.ctx)
    if handler is not None:
        handler.queue_energy_link_withdraw(self.ctx, "heal", 20, ENERGY_LINK_HEAL_20_COST)


def cmd_smash64_el_heal50(self) -> None:
    """Spend 50 EnergyLink to heal 50%."""
    handler = _smash64_energylink_handler(self.ctx)
    if handler is not None:
        handler.queue_energy_link_withdraw(self.ctx, "heal", 50, ENERGY_LINK_HEAL_50_COST)


def cmd_smash64_el_stock(self) -> None:
    """Spend 50 EnergyLink to gain one stock in the current/next Classic fight."""
    handler = _smash64_energylink_handler(self.ctx)
    if handler is not None:
        handler.queue_energy_link_withdraw(self.ctx, "stock", 1, ENERGY_LINK_STOCK_COST)


def install_smash64_command_processor(ctx: "BizHawkClientContext") -> None:
    """Register Smash64-specific local BizHawk client commands."""
    commands = getattr(getattr(ctx, "command_processor", None), "commands", None)
    if commands is None:
        return

    commands["characters"] = cmd_smash64_characters
    commands["deathlink"] = cmd_smash64_deathlink
    commands["energylink"] = cmd_smash64_energylink
    commands["goal"] = cmd_smash64_goal
    commands["el_heal5"] = cmd_smash64_el_heal5
    commands["el_heal10"] = cmd_smash64_el_heal10
    commands["el_heal20"] = cmd_smash64_el_heal20
    commands["el_heal50"] = cmd_smash64_el_heal50
    commands["el_stock"] = cmd_smash64_el_stock



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
    snapshot_difficulty: int | None
    snapshot_btt_char: int | None
    last_classic_fight_char: int | None
    processed_received_item_count: int | None
    pending_health_delta: int
    pending_stock_delta: int
    health_effect_value: int | None
    health_effect_frames: int
    death_link_enabled: bool
    death_link_user_enabled: bool
    death_link_status_sent: bool
    damage_link_enabled: bool
    damage_link_status_sent: bool
    last_damage_percent: int | None
    pending_damage_link_hits: int
    damage_link_send_bucket: int | None
    energy_link_enabled: bool
    energy_link_status_sent: bool
    energy_link_notify_sent: bool
    energy_link_value: int
    energy_link_spent_pending_reply: int
    pending_energy_link_withdraws: list[tuple[str, int, int]]
    last_stock_value: int | None
    last_max_stock_cap_value: int | None
    last_difficulty_cap_value: int | None
    last_selected_difficulty_value: int | None
    sent_deathlink_for_current_stockout: bool
    pending_deathlinks: int
    last_deathlink_time: float
    goal_sent: bool
    last_locked_hover_display_value: int | None
    last_locked_hover_display_time: float

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
        self.snapshot_difficulty = None
        self.snapshot_btt_char = None
        self.last_classic_fight_char = None
        self.processed_received_item_count = None
        self.pending_health_delta = 0
        self.pending_stock_delta = 0
        self.health_effect_value = None
        self.health_effect_frames = 0
        self.death_link_enabled = False
        self.death_link_user_enabled = True
        self.death_link_status_sent = False
        self.damage_link_enabled = False
        self.damage_link_status_sent = False
        self.last_damage_percent = None
        self.pending_damage_link_hits = 0
        self.damage_link_send_bucket = None
        self.damage_link_last_send_time = 0.0
        self.damage_link_block_until = 0.0
        self.damage_link_fight_started_at = 0.0
        self.energy_link_enabled = False
        self.energy_link_status_sent = False
        self.energy_link_notify_sent = False
        self.energy_link_value = 0
        self.energy_link_spent_pending_reply = 0
        self.pending_energy_link_withdraws = []
        self.last_stock_value = None
        self.last_max_stock_cap_value = None
        self.last_difficulty_cap_value = None
        self.last_selected_difficulty_value = None
        self.sent_deathlink_for_current_stockout = False
        self.pending_deathlinks = 0
        self.last_deathlink_time = 0.0
        self.goal_sent = False
        self.last_locked_hover_display_value = None
        self.last_locked_hover_display_time = 0.0

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
        ctx.client_handler = self
        install_smash64_command_processor(ctx)
        # Full item handling is required so Fighter Passes found in your own world
        # are delivered to ctx.items_received and unlock characters.
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
        self.snapshot_difficulty = None
        self.snapshot_btt_char = None
        self.last_classic_fight_char = None
        self.processed_received_item_count = None
        self.pending_health_delta = 0
        self.pending_stock_delta = 0
        self.health_effect_value = None
        self.health_effect_frames = 0
        self.death_link_enabled = False
        self.death_link_user_enabled = True
        self.death_link_status_sent = False
        self.damage_link_enabled = False
        self.damage_link_status_sent = False
        self.last_damage_percent = None
        self.pending_damage_link_hits = 0
        self.damage_link_send_bucket = None
        self.damage_link_last_send_time = 0.0
        self.damage_link_block_until = 0.0
        self.damage_link_fight_started_at = 0.0
        self.energy_link_enabled = False
        self.energy_link_status_sent = False
        self.energy_link_notify_sent = False
        self.energy_link_value = 0
        self.energy_link_spent_pending_reply = 0
        self.pending_energy_link_withdraws = []
        self.last_stock_value = None
        self.last_max_stock_cap_value = None
        self.sent_deathlink_for_current_stockout = False
        self.pending_deathlinks = 0
        self.last_deathlink_time = 0.0
        self.goal_sent = False
        self.last_locked_hover_display_value = None
        self.last_locked_hover_display_time = 0.0
        try:
            await bizhawk.set_message_interval(ctx.bizhawk_ctx, 0.05)
        except bizhawk.RequestFailedError:
            pass
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        if self.player_name:
            ctx.auth = self.player_name

    def get_enabled_character_names(self, ctx: "BizHawkClientContext") -> Set[str]:
        """Return the characters included by this seed's character_checks option.

        Older seeds did not send this slot-data field, so default to all
        characters for compatibility.
        """
        slot_data = getattr(ctx, "slot_data", None) or {}
        raw_characters = slot_data.get("characters", None)
        if raw_characters is None:
            return set(CHARACTERS)

        enabled = {name for name in raw_characters if name in CHARACTER_SELECT_VALUE_BY_NAME}
        return enabled or set(CHARACTERS)

    def get_enabled_character_values(self, ctx: "BizHawkClientContext") -> Set[int]:
        return {
            CHARACTER_SELECT_VALUE_BY_NAME[name]
            for name in self.get_enabled_character_names(ctx)
            if name in CHARACTER_SELECT_VALUE_BY_NAME
        }


    def _character_from_received_item(self, ctx: "BizHawkClientContext", item_id: int) -> str | None:
        """Return the Smash64 character unlocked by a received Fighter Pass.

        Older/newer builds have changed the item table a few times, so do not
        rely only on the local hard-coded numeric map.  First try the exact
        current numeric ID map, then fall back to Archipelago's item-name
        lookup and parse names like "Fox Fighter Pass".
        """
        character = CHARACTER_BY_ITEM_ID.get(item_id)
        if character is not None:
            return character

        item_name = None
        item_names = getattr(ctx, "item_names", None)
        if item_names is not None:
            for method_name in ("lookup_in_game", "lookup_in_slot", "lookup_in_world"):
                method = getattr(item_names, method_name, None)
                if method is None:
                    continue
                try:
                    if method_name == "lookup_in_slot":
                        item_name = method(item_id, getattr(ctx, "slot", None))
                    else:
                        item_name = method(item_id)
                except Exception:
                    item_name = None
                if item_name:
                    break

        if isinstance(item_name, str) and item_name.endswith(" Fighter Pass"):
            candidate = item_name[:-len(" Fighter Pass")]
            if candidate in CHARACTER_SELECT_VALUE_BY_NAME:
                return candidate

        return None

    def get_unlocked_character_names(self, ctx: "BizHawkClientContext") -> Set[str]:
        unlocked: Set[str] = set()
        enabled = self.get_enabled_character_names(ctx)

        slot_data = getattr(ctx, "slot_data", None) or {}
        starting_character = slot_data.get("starting_character", "Mario")
        if starting_character in enabled and starting_character in CHARACTER_SELECT_VALUE_BY_NAME:
            unlocked.add(starting_character)

        for network_item in getattr(ctx, "items_received", []):
            character = self._character_from_received_item(ctx, int(network_item.item))
            if character is not None and character in enabled:
                unlocked.add(character)

        if not unlocked:
            # Compatibility / malformed slot data fallback. Prefer the first
            # enabled character in the game's stable character order.
            for character in CHARACTERS:
                if character in enabled:
                    unlocked.add(character)
                    break

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

    def _get_character_fallback_value(self, ctx: "BizHawkClientContext") -> int | None:
        unlocked_names = self.get_unlocked_character_names(ctx)
        unlocked_values = {
            CHARACTER_SELECT_VALUE_BY_NAME[name]
            for name in unlocked_names
            if name in CHARACTER_SELECT_VALUE_BY_NAME
        }
        if not unlocked_values:
            return None

        slot_data = getattr(ctx, "slot_data", None) or {}
        starting_character = slot_data.get("starting_character", "Mario")
        fallback_value = CHARACTER_SELECT_VALUE_BY_NAME.get(starting_character)
        if fallback_value not in unlocked_values:
            fallback_value = min(unlocked_values)

        return fallback_value

    async def _force_btt_character_from_last_classic_fight(
        self,
        ctx: "BizHawkClientContext",
        current_btt_char: int,
    ) -> int:
        forced_char = self.last_classic_fight_char

        # If BTT loads before we have seen a normal Classic fight in this client
        # session, fall back to the current AP-legal character instead of the raw
        # character-select value.
        if forced_char not in CHARACTER_NAME_BY_SELECT_VALUE:
            forced_char = self._get_character_fallback_value(ctx)

        if forced_char in CHARACTER_NAME_BY_SELECT_VALUE and current_btt_char != forced_char:
            await self._burst_write_u8(ctx, BTT_CHAR_ADDR, forced_char, repeats=16)
            return forced_char

        return current_btt_char

    async def _display_locked_hover_message(
        self,
        ctx: "BizHawkClientContext",
        current_value: int,
        unlocked_values: Set[int],
    ) -> None:
        """Show an on-screen LOCKED warning when hovering a locked character.

        The old /characters command was not reliable for the user's setup, so this
        uses BizHawk's connector overlay instead. We throttle it so it stays visible
        while hovering a locked fighter without flooding the connector.
        """
        now = time.monotonic()

        if current_value not in CHARACTER_NAME_BY_SELECT_VALUE or current_value in unlocked_values:
            self.last_locked_hover_display_value = None
            return

        # Re-send while hovering the same locked character often enough to keep
        # the message visible, but not every watcher tick.
        if (
            self.last_locked_hover_display_value == current_value
            and now - self.last_locked_hover_display_time < 0.35
        ):
            return

        self.last_locked_hover_display_value = current_value
        self.last_locked_hover_display_time = now
        await bizhawk.display_message(ctx.bizhawk_ctx, "LOCKED")

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

        current_css_value = (await bizhawk.read(ctx.bizhawk_ctx, [
            (P1_CHARACTER_SELECT_ADDR, 1, "RDRAM"),
        ]))[0][0]
        await self._display_locked_hover_message(ctx, current_css_value, unlocked_values)

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


    def _is_classic_fight_state(self, game_state: int, stage_id: int) -> bool:
        """True only during normal Classic opponent fights.

        This deliberately excludes menus, loading, results, and Break the Targets.
        """
        return game_state == STATE_IN_BATTLE and stage_id in CLASSIC_FIGHT_NAME_BY_STAGE_ID

    async def _sync_death_link_status(self, ctx: "BizHawkClientContext") -> None:
        """Keep the room/server DeathLink tag in sync with the slot option.

        The previous build only tried to set the tag once, and preferred
        ctx.update_death_link when present. On AP 0.6.7 that did not reliably
        make the web room show the DeathLink tag for this custom BizHawk
        client. This now mirrors the working Pokémon Platinum style: mutate
        ctx.tags directly and send ConnectUpdate whenever the desired tag set
        differs from the current one.
        """
        slot_data = getattr(ctx, "slot_data", None) or {}
        slot_enabled = bool(slot_data.get("death_link", False))
        enabled = bool(slot_enabled and self.death_link_user_enabled)
        self.death_link_enabled = enabled

        desired_tags = set(getattr(ctx, "tags", set()) or set())
        if enabled:
            desired_tags.add("DeathLink")
        else:
            desired_tags.discard("DeathLink")

        current_tags = set(getattr(ctx, "tags", set()) or set())
        if current_tags != desired_tags or not self.death_link_status_sent:
            ctx.tags = desired_tags
            if getattr(ctx, "server", None) and getattr(ctx.server, "socket", None) and not ctx.server.socket.closed:
                await ctx.send_msgs([{"cmd": "ConnectUpdate", "tags": list(desired_tags)}])
            self.death_link_status_sent = True

    async def _sync_damage_link_status(self, ctx: "BizHawkClientContext") -> None:
        """Keep the room/server SharedDamage tag in sync with the slot option."""
        slot_data = getattr(ctx, "slot_data", None) or {}
        enabled = bool(slot_data.get("damage_link", False))
        self.damage_link_enabled = enabled

        desired_tags = set(getattr(ctx, "tags", set()) or set())
        if enabled:
            desired_tags.add("SharedDamage")
        else:
            desired_tags.discard("SharedDamage")

        current_tags = set(getattr(ctx, "tags", set()) or set())
        if current_tags != desired_tags or not self.damage_link_status_sent:
            ctx.tags = desired_tags
            if getattr(ctx, "server", None) and getattr(ctx.server, "socket", None) and not ctx.server.socket.closed:
                await ctx.send_msgs([{"cmd": "ConnectUpdate", "tags": list(desired_tags)}])
            self.damage_link_status_sent = True

    async def _sync_energy_link_status(self, ctx: "BizHawkClientContext") -> None:
        """Keep the room/server EnergyLink tag and data-storage subscription in sync."""
        slot_data = getattr(ctx, "slot_data", None) or {}
        enabled = bool(slot_data.get("energy_link", False))
        self.energy_link_enabled = enabled

        desired_tags = set(getattr(ctx, "tags", set()) or set())
        if enabled:
            desired_tags.add("EnergyLink")
        else:
            desired_tags.discard("EnergyLink")

        current_tags = set(getattr(ctx, "tags", set()) or set())
        if current_tags != desired_tags or not self.energy_link_status_sent:
            ctx.tags = desired_tags
            if getattr(ctx, "server", None) and getattr(ctx.server, "socket", None) and not ctx.server.socket.closed:
                await ctx.send_msgs([{"cmd": "ConnectUpdate", "tags": list(desired_tags)}])
            self.energy_link_status_sent = True

        if enabled and not self.energy_link_notify_sent:
            if getattr(ctx, "server", None) and getattr(ctx.server, "socket", None) and not ctx.server.socket.closed:
                await ctx.send_msgs([
                    {"cmd": "SetNotify", "keys": [_energy_link_key(ctx)]},
                    {"cmd": "Get", "keys": [_energy_link_key(ctx)]},
                ])
                self.energy_link_notify_sent = True
        elif not enabled:
            self.energy_link_notify_sent = False
            self.pending_energy_link_withdraws.clear()

    async def _deposit_energy_link(self, ctx: "BizHawkClientContext", amount: int) -> None:
        if amount <= 0 or not self.energy_link_enabled:
            return
        if not (getattr(ctx, "server", None) and getattr(ctx.server, "socket", None) and not ctx.server.socket.closed):
            return
        await ctx.send_msgs([{
            "cmd": "Set",
            "key": _energy_link_key(ctx),
            "default": 0,
            "want_reply": True,
            "operations": [{"operation": "add", "value": int(amount)}],
        }])
        from CommonClient import logger
        logger.info(f"[Smash64] Deposited {int(amount)} EnergyLink.")

    async def _spend_energy_link(self, ctx: "BizHawkClientContext", amount: int) -> bool:
        if amount <= 0 or not self.energy_link_enabled:
            return False
        if self.energy_link_value - self.energy_link_spent_pending_reply < amount:
            return False
        if not (getattr(ctx, "server", None) and getattr(ctx.server, "socket", None) and not ctx.server.socket.closed):
            return False
        self.energy_link_spent_pending_reply += amount
        await ctx.send_msgs([{
            "cmd": "Set",
            "key": _energy_link_key(ctx),
            "default": 0,
            "want_reply": True,
            "operations": [{"operation": "add", "value": -int(amount)}],
        }])
        return True

    def queue_energy_link_withdraw(self, ctx: "BizHawkClientContext", effect_type: str, amount: int, cost: int) -> None:
        """Called by local /el_* commands. The actual write waits for a fight."""
        from CommonClient import logger

        slot_data = getattr(ctx, "slot_data", None) or {}
        if not bool(slot_data.get("energy_link", False)):
            logger.info("EnergyLink is disabled in this seed. Set energy_link: true in the YAML.")
            return
        if not self.energy_link_enabled:
            logger.info("EnergyLink is not connected/synced yet. Try again after connecting.")
            return
        available = self.energy_link_value - self.energy_link_spent_pending_reply
        if available < cost:
            logger.info(f"Not enough EnergyLink. Need {cost}, have {max(0, available)}.")
            return

        self.pending_energy_link_withdraws.append((effect_type, int(amount), int(cost)))
        logger.info(f"Queued EnergyLink {effect_type} {amount} for {cost}. It will apply in a Classic fight.")

    async def handle_energy_link(self, ctx: "BizHawkClientContext") -> None:
        await self._sync_energy_link_status(ctx)
        if not self.energy_link_enabled:
            return
        if not self.pending_energy_link_withdraws:
            return

        game_state, stage_id = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (CLASSIC_STAGE_ADDR, 1, "RDRAM"),
        ])]
        if not self._is_classic_fight_state(game_state, stage_id):
            return

        remaining_withdraws: list[tuple[str, int, int]] = []
        for effect_type, amount, cost in self.pending_energy_link_withdraws:
            spent = await self._spend_energy_link(ctx, cost)
            if not spent:
                remaining_withdraws.append((effect_type, amount, cost))
                continue

            if effect_type == "heal":
                # Smash percent is damage, so healing subtracts damage percent.
                self.pending_health_delta -= amount
            elif effect_type == "stock":
                self.pending_stock_delta += amount

        self.pending_energy_link_withdraws = remaining_withdraws

    async def _send_damage_link(self, ctx: "BizHawkClientContext", damage_points: int) -> None:
        if damage_points <= 0:
            return
        source = getattr(ctx, "auth", None) or self.player_name or "Super Smash Bros. 64 Player"
        await ctx.send_msgs([{
            "cmd": "Bounce",
            "tags": ["SharedDamage"],
            "data": {
                "time": time.time(),
                "uuid": Utils.get_unique_identifier(),
                "source": source,
                "damage_points": int(damage_points),
            },
        }])
        from CommonClient import logger
        logger.info(f"[Smash64] Sent DamageLink bounce packet: {int(damage_points)} damage points.")

    async def _send_death_link(self, ctx: "BizHawkClientContext") -> None:
        source = getattr(ctx, "auth", None) or self.player_name or "Super Smash Bros. 64 Player"
        await ctx.send_msgs([{
            "cmd": "Bounce",
            "tags": ["DeathLink"],
            "data": {
                "time": time.time(),
                "source": source,
                "cause": f"{source} Picked a Fight with gravity, and lost!",
            },
        }])

    def _get_max_stock_cap_value(self, ctx: "BizHawkClientContext") -> int:
        """Return the highest allowed stock selector value.

        Smash 64 stores stock count as:
            0 = 1 stock
            1 = 2 stocks
            2 = 3 stocks
            3 = 4 stocks
            4 = 5 stocks

        The player starts capped at 0. Each Progressive Max Stocks item raises
        the cap by one, maxing at 4.
        """
        # Slot data stores the YAML option as the human stock count, 1-5.
        # The game stores the selector as 0-4, so convert by subtracting 1.
        slot_data = getattr(ctx, "slot_data", None) or {}
        starting_max_stocks = int(slot_data.get("starting_max_stocks", 1) or 1)
        base_cap = max(0, min(4, starting_max_stocks - 1))

        count = 0
        for network_item in getattr(ctx, "items_received", []):
            if network_item.item == PROGRESSIVE_MAX_STOCKS_ID:
                count += 1
        return max(0, min(4, base_cap + count))

    async def handle_progressive_max_stocks(self, ctx: "BizHawkClientContext") -> None:
        max_allowed = self._get_max_stock_cap_value(ctx)
        self.last_max_stock_cap_value = max_allowed

        current_select = (await bizhawk.read(ctx.bizhawk_ctx, [
            (MAX_STOCKS_SELECT_ADDR, 1, "RDRAM"),
        ]))[0][0]

        # Clamp the Classic stock selector/menu value. If the player tries to
        # choose more stocks than AP currently allows, force it back down.
        if 0 <= current_select <= 4 and current_select > max_allowed:
            await self._burst_write_u8(ctx, MAX_STOCKS_SELECT_ADDR, max_allowed, repeats=12)

        # Do not clamp the in-fight stock byte here. Extra Stock is allowed to
        # raise the current fight's stocks above the AP max-stock cap. The cap
        # only controls the Classic stock selector before the fight begins.

    def _get_enabled_difficulty_values(self, ctx: "BizHawkClientContext") -> set[int]:
        """Return the exact Classic difficulties included by the YAML.

        Values match Smash 64's selector byte:
            0 = Very Easy, 1 = Easy, 2 = Normal, 3 = Hard, 4 = Very Hard
        """
        slot_data = getattr(ctx, "slot_data", None) or {}
        raw_values = slot_data.get("difficulty_checks", None)

        if raw_values is None:
            # Compatibility with older generated seeds.
            max_value = int(slot_data.get("max_difficulty_checks", 4))
            return {value for value in range(0, max(0, min(4, max_value)) + 1)}

        values = set()
        for value in raw_values:
            try:
                difficulty_value = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= difficulty_value <= 4:
                values.add(difficulty_value)

        return values or {0}

    def _get_difficulty_cap_value(self, ctx: "BizHawkClientContext") -> int:
        """Return the highest currently unlocked Classic difficulty value.

        difficulty_checks may start above Very Easy. In that case the apworld
        precollects enough Progressive Difficulty items and also sends
        starting_difficulty_cap in slot data, so the client does not force the
        selector down to Very Easy for hard-only/normal-only seeds.
        """
        slot_data = getattr(ctx, "slot_data", None) or {}
        base_cap = int(slot_data.get("starting_difficulty_cap", 0))

        count = 0
        for network_item in getattr(ctx, "items_received", []):
            if network_item.item == PROGRESSIVE_DIFFICULTY_ID:
                count += 1
        return max(0, min(4, base_cap + count))

    def _get_allowed_difficulty_for_selector(self, ctx: "BizHawkClientContext") -> int:
        """Return the highest YAML-enabled difficulty that is currently unlocked."""
        enabled = sorted(self._get_enabled_difficulty_values(ctx))
        cap = self._get_difficulty_cap_value(ctx)

        unlocked_enabled = [value for value in enabled if value <= cap]
        if unlocked_enabled:
            return max(unlocked_enabled)

        # This should only happen with malformed slot data. Prefer the lowest
        # enabled difficulty over a difficulty that has no checks.
        return min(enabled)

    async def handle_progressive_difficulty(self, ctx: "BizHawkClientContext") -> None:
        max_allowed = self._get_difficulty_cap_value(ctx)
        self.last_difficulty_cap_value = max_allowed

        enabled = self._get_enabled_difficulty_values(ctx)
        target_select = self._get_allowed_difficulty_for_selector(ctx)

        game_state, current_select = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (DIFFICULTY_SELECT_ADDR, 1, "RDRAM"),
        ])]

        # 0x138FB7 is the menu difficulty selector. During the actual Classic
        # fight/result screens the byte can read back as 0, which made every
        # clear look like Very Easy. Only learn the selected difficulty while
        # we are outside Classic gameplay states; then the fight-check handler
        # snapshots this remembered value when the battle starts.
        in_classic_gameplay_state = game_state in {STATE_IN_BATTLE, STATE_LOADING, STATE_RESULTS, STATE_BTT}

        # Force the Classic difficulty selector to one of the exact YAML-enabled
        # difficulties. Also prevent selecting an enabled difficulty before the
        # corresponding Progressive Difficulty cap has been reached.
        if 0 <= current_select <= 4 and (current_select not in enabled or current_select > max_allowed):
            await self._burst_write_u8(ctx, DIFFICULTY_SELECT_ADDR, target_select, repeats=12)
            if not in_classic_gameplay_state:
                self.last_selected_difficulty_value = target_select
        elif 0 <= current_select <= 4 and current_select in enabled and current_select <= max_allowed:
            if not in_classic_gameplay_state:
                self.last_selected_difficulty_value = current_select

        if self.last_selected_difficulty_value is None:
            self.last_selected_difficulty_value = target_select

    async def handle_death_link(self, ctx: "BizHawkClientContext") -> None:
        await self._sync_death_link_status(ctx)
        if not self.death_link_enabled:
            return

        game_state, stage_id, stocks = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (CLASSIC_STAGE_ADDR, 1, "RDRAM"),
            (P1_STOCKS_ADDR, 1, "RDRAM"),
        ])]

        in_classic_fight = self._is_classic_fight_state(game_state, stage_id)

        # Send DeathLink only when the stock byte becomes 255 during a Classic fight.
        if in_classic_fight:
            if (
                stocks == 0xFF
                and self.last_stock_value is not None
                and self.last_stock_value != 0xFF
                and not self.sent_deathlink_for_current_stockout
            ):
                await self._send_death_link(ctx)
                self.sent_deathlink_for_current_stockout = True

            if stocks != 0xFF:
                self.sent_deathlink_for_current_stockout = False

            # Apply received DeathLinks only during Classic fights. The stock byte is:
            #   0   = one life left
            #   1-4 = two to five stocks left
            #   255 = zero stocks / already dead
            # So DeathLink only lowers values 1..4 by one. Ignore 0 and 255.
            while self.pending_deathlinks > 0:
                current_stocks = (await bizhawk.read(ctx.bizhawk_ctx, [(P1_STOCKS_ADDR, 1, "RDRAM")]))[0][0]
                if current_stocks == 0 or current_stocks == 0xFF:
                    self.pending_deathlinks -= 1
                    break

                if 1 <= current_stocks <= 4:
                    new_stocks = current_stocks - 1
                    await self._burst_write_u8(ctx, P1_STOCKS_ADDR, new_stocks, repeats=12)

                self.pending_deathlinks -= 1

        self.last_stock_value = stocks

    async def on_package(self, ctx: "BizHawkClientContext", cmd: str, args: dict) -> None:
        if cmd == "Retrieved":
            keys = args.get("keys", {}) or {}
            energy_key = _energy_link_key(ctx)
            if energy_key in keys:
                try:
                    self.energy_link_value = int(keys.get(energy_key, 0) or 0)
                except (TypeError, ValueError):
                    self.energy_link_value = 0
            return

        if cmd == "SetReply" and args.get("key") == _energy_link_key(ctx):
            try:
                self.energy_link_value = int(args.get("value", 0) or 0)
            except (TypeError, ValueError):
                self.energy_link_value = 0
            # A SetReply for our spend/deposit means the server has caught up;
            # clear local pending spend accounting so commands see the real balance.
            self.energy_link_spent_pending_reply = 0
            return

        if cmd != "Bounced":
            return

        tags = args.get("tags", []) or []
        data = args.get("data", {}) or {}
        source = data.get("source")
        own_source = getattr(ctx, "auth", None) or self.player_name

        if "DeathLink" in tags and self.death_link_enabled:
            death_time = float(data.get("time", 0.0) or 0.0)
            if death_time <= self.last_deathlink_time:
                return

            self.last_deathlink_time = death_time
            if source != own_source:
                self.pending_deathlinks += 1
            return

        if "SharedDamage" in tags and self.damage_link_enabled:
            if source == own_source:
                return

            try:
                damage_points = int(data.get("damage_points", 0) or 0)
            except (TypeError, ValueError):
                return

            # In this Smash 64 implementation, each received SharedDamage packet
            # applies exactly +1% damage, regardless of the packet's damage_points.
            # The value only needs to be a positive integer to be accepted.
            if damage_points > 0:
                self.pending_damage_link_hits += 1

    async def _send_location_check_once(self, ctx: "BizHawkClientContext", location_id: int) -> bool:
        already_checked = set(getattr(ctx, "checked_locations", set()))
        already_checked.update(getattr(ctx, "locations_checked", set()))
        if location_id not in self.local_checked_locations and location_id not in already_checked:
            self.local_checked_locations.add(location_id)
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": [location_id]}])
            # Hard failsafe: after any check is sent, do not allow DamageLink
            # to send from stale/inter-stage damage changes for 30 seconds.
            self.damage_link_block_until = time.monotonic() + DAMAGE_LINK_AFTER_CHECK_BLOCK_SECONDS
            self.last_damage_percent = None
            self.damage_link_send_bucket = None
            return True
        return False

    async def _write_p1_percent_damage(self, ctx: "BizHawkClientContext", value: int, repeats: int = 8) -> None:
        """Write the P1 percent/damage byte through both useful BizHawk domains.

        The address found in Lua is a main-memory/RDRAM address. Some BizHawk
        bridge builds expose the same live byte more reliably through the N64
        CPU/System Bus mirror at 0x80xxxxxx, so write both.
        """
        value_byte = bytes([value & 0xFF])
        for _ in range(repeats):
            await bizhawk.write(ctx.bizhawk_ctx, [
                (P1_HEALTH_ADDR, value_byte, "RDRAM"),
            ])
            try:
                await bizhawk.write(ctx.bizhawk_ctx, [
                    (P1_HEALTH_SYSTEM_BUS_ADDR, value_byte, "System Bus"),
                ])
            except bizhawk.RequestFailedError:
                pass

    async def handle_damage_link(self, ctx: "BizHawkClientContext") -> None:
        await self._sync_damage_link_status(ctx)
        if not self.damage_link_enabled:
            self.last_damage_percent = None
            self.damage_link_send_bucket = None
            return

        game_state, current_damage = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (P1_HEALTH_ADDR, 1, "RDRAM"),
        ])]

        now = time.monotonic()

        # Only watch/send during real fights. Any other state resets the damage
        # baseline so menu/results/loading memory cannot produce bounce spam.
        if game_state != STATE_IN_BATTLE:
            self.last_damage_percent = None
            self.damage_link_send_bucket = None
            self.damage_link_fight_started_at = 0.0
            return

        if self.damage_link_fight_started_at <= 0.0:
            self.damage_link_fight_started_at = now
            self.last_damage_percent = int(current_damage)
            self.damage_link_send_bucket = int(current_damage) // 10
            return

        current_damage = int(current_damage)
        current_bucket = current_damage // 10

        if self.last_damage_percent is None:
            self.last_damage_percent = current_damage
            self.damage_link_send_bucket = current_bucket
        elif current_damage < self.last_damage_percent:
            # Damage decreased because of healing/new stock/new fight; reset baseline.
            self.last_damage_percent = current_damage
            self.damage_link_send_bucket = current_bucket
        else:
            previous_bucket = self.damage_link_send_bucket
            if previous_bucket is None:
                previous_bucket = self.last_damage_percent // 10

            crossed_ten_percent = current_bucket > previous_bucket
            cooldown_ready = now >= self.damage_link_block_until and now >= (self.damage_link_last_send_time + DAMAGE_LINK_SEND_COOLDOWN_SECONDS)
            fight_grace_over = now >= (self.damage_link_fight_started_at + DAMAGE_LINK_FIGHT_START_GRACE_SECONDS)

            if crossed_ten_percent:
                # Always move the bucket forward, even if cooldown blocks the send.
                # This prevents one old threshold crossing from firing later between
                # stages or after the 30 second post-check block expires.
                self.damage_link_send_bucket = current_bucket

                if cooldown_ready and fight_grace_over:
                    await self._send_damage_link(ctx, 10)
                    self.damage_link_last_send_time = now

            self.last_damage_percent = current_damage

        # Receiving DamageLink is independent from sending cooldowns. Each valid
        # SharedDamage packet adds exactly 1% damage once the player is in a fight.
        while self.pending_damage_link_hits > 0:
            live_damage = (await bizhawk.read(ctx.bizhawk_ctx, [(P1_HEALTH_ADDR, 1, "RDRAM")]))[0][0]
            new_damage = max(0, min(255, live_damage + 1))
            await self._write_p1_percent_damage(ctx, new_damage, repeats=8)
            self.pending_damage_link_hits -= 1
            self.last_damage_percent = new_damage
            self.damage_link_send_bucket = new_damage // 10

    async def handle_health_effect_items(self, ctx: "BizHawkClientContext") -> None:
        """Queue health/damage filler effects and apply them once P1 is in a fight.

        Smash 64 percent is damage, not HP: Healing Cheers subtracts 5 from
        damage percent, while Heckling Crowd adds 5. Effects are queued until
        normal fight state 0x01, then the target value is forced for a short
        burst so the game cannot immediately overwrite a one-frame write.
        """
        items_received = list(getattr(ctx, "items_received", []))

        if self.processed_received_item_count is None:
            # Start at 0 so a health/trap item that arrived before the first
            # watcher tick still gets queued and applied when the fight starts.
            self.processed_received_item_count = 0

        for network_item in items_received[self.processed_received_item_count:]:
            if network_item.item == HEALING_CHEERS_ID:
                self.pending_health_delta -= 5
            elif network_item.item == HECKLING_CROWD_ID:
                self.pending_health_delta += 5
            elif network_item.item == EXTRA_STOCK_ID:
                self.pending_stock_delta += 1
            elif network_item.item == STOCK_THIEF_ID:
                self.pending_stock_delta -= 1

        self.processed_received_item_count = len(items_received)

        game_state, stage_id = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (CLASSIC_STAGE_ADDR, 1, "RDRAM"),
        ])]
        if not self._is_classic_fight_state(game_state, stage_id):
            return

        # Continue forcing the last target value for a few frames. This matches
        # how the Lua tests win timing-sensitive writes by running every frame.
        if self.health_effect_frames > 0 and self.health_effect_value is not None:
            await self._write_p1_percent_damage(ctx, self.health_effect_value, repeats=4)
            self.health_effect_frames -= 1
            if self.health_effect_frames <= 0:
                self.health_effect_value = None
        elif self.pending_health_delta != 0:
            current_health = (await bizhawk.read(ctx.bizhawk_ctx, [(P1_HEALTH_ADDR, 1, "RDRAM")]))[0][0]
            new_health = max(0, min(255, current_health + self.pending_health_delta))

            self.pending_health_delta = 0
            self.health_effect_value = new_health
            self.health_effect_frames = 30
            await self._write_p1_percent_damage(ctx, new_health, repeats=12)

        if self.pending_stock_delta != 0:
            current_stocks = (await bizhawk.read(ctx.bizhawk_ctx, [(P1_STOCKS_ADDR, 1, "RDRAM")]))[0][0]

            # Stock byte range:
            #   0   = one life left
            #   1-4 = two to five stocks left
            #   255 = zero stocks / already dead
            # Extra Stock can raise the current fight above the AP max-stock cap,
            # but still clamps to the game's normal max value 4. Stock Thief
            # removes one current-fight stock and ignores 0/255.
            if current_stocks != 0xFF:
                if self.pending_stock_delta > 0:
                    new_stocks = max(0, min(4, current_stocks + self.pending_stock_delta))
                    await self._burst_write_u8(ctx, P1_STOCKS_ADDR, new_stocks, repeats=12)
                    self.pending_stock_delta = 0
                elif self.pending_stock_delta < 0:
                    if 1 <= current_stocks <= 4:
                        new_stocks = current_stocks - 1
                        await self._burst_write_u8(ctx, P1_STOCKS_ADDR, new_stocks, repeats=12)
                    self.pending_stock_delta += 1

    async def handle_classic_stage_checks(self, ctx: "BizHawkClientContext") -> None:
        game_state, stage_id, char_id, difficulty_value, btt_char_id = [x[0] for x in await bizhawk.read(ctx.bizhawk_ctx, [
            (GAME_STATE_ADDR, 1, "RDRAM"),
            (CLASSIC_STAGE_ADDR, 1, "RDRAM"),
            (CLASSIC_CHAR_ADDR, 1, "RDRAM"),
            (DIFFICULTY_SELECT_ADDR, 1, "RDRAM"),
            (BTT_CHAR_ADDR, 1, "RDRAM"),
        ])]

        if difficulty_value not in DIFFICULTY_NAME_BY_VALUE:
            difficulty_value = 0

        self.last_seen_game_state = game_state

        # Normal Classic fight checks: snapshot the character/stage when battle starts,
        # then send the mapped opponent check when results appears.
        if game_state == STATE_IN_BATTLE and self.prev_game_state != STATE_IN_BATTLE:
            self.snapshot_stage = stage_id
            self.snapshot_char = char_id

            # Use the remembered menu difficulty, not the raw selector byte while
            # in battle. The raw byte can become 0 in fights, which incorrectly
            # sends only Very Easy checks.
            enabled_difficulties = self._get_enabled_difficulty_values(ctx)
            remembered_difficulty = self.last_selected_difficulty_value
            if remembered_difficulty not in enabled_difficulties:
                remembered_difficulty = self._get_allowed_difficulty_for_selector(ctx)
            self.snapshot_difficulty = remembered_difficulty

            if char_id in CHARACTER_NAME_BY_SELECT_VALUE and stage_id in CLASSIC_FIGHT_NAME_BY_STAGE_ID:
                self.last_classic_fight_char = char_id

        if game_state == STATE_RESULTS and self.prev_game_state != STATE_RESULTS:
            if self.snapshot_stage is not None and self.snapshot_char is not None and self.snapshot_difficulty is not None:
                enabled_difficulties = self._get_enabled_difficulty_values(ctx)
                enabled_character_values = self.get_enabled_character_values(ctx)

                if self.snapshot_char not in enabled_character_values:
                    self.snapshot_stage = None
                    self.snapshot_char = None
                    self.snapshot_difficulty = None
                    self.prev_game_state = game_state
                    await self.check_goal(ctx)
                    return

                # Only send Classic fight checks for the exact YAML-selected
                # difficulties. Example: difficulty_checks: [hard] sends only
                # Hard fight locations, not Very Easy/Easy/Normal.
                if self.snapshot_difficulty in enabled_difficulties:
                    location_id = location_id_by_character_stage_and_difficulty.get((
                        self.snapshot_char,
                        self.snapshot_stage,
                        self.snapshot_difficulty,
                    ))
                    if location_id is not None:
                        await self._send_location_check_once(ctx, location_id)
                        # EnergyLink is awarded for clearing fights, not only for
                        # first-time AP location checks. This keeps repeated clears
                        # and already-checked locations from silently paying nothing.
                        await self._deposit_energy_link(ctx, ENERGY_LINK_FIGHT_DEPOSIT)
                        if CLASSIC_FIGHT_NAME_BY_STAGE_ID.get(self.snapshot_stage) == "Master Hand":
                            await self._deposit_energy_link(ctx, ENERGY_LINK_CLASSIC_CLEAR_DEPOSIT)

                    # Optional convenience: clearing a fight on a higher selected
                    # difficulty also sends the same character/fight check on
                    # lower selected difficulties. This only sends locations that
                    # actually exist in the current seed via difficulty_checks.
                    slot_data = getattr(ctx, "slot_data", None) or {}
                    if bool(slot_data.get("auto_check_lower_difficulties", False)):
                        for lower_difficulty in sorted(enabled_difficulties):
                            if lower_difficulty >= self.snapshot_difficulty:
                                continue

                            lower_location_id = location_id_by_character_stage_and_difficulty.get((
                                self.snapshot_char,
                                self.snapshot_stage,
                                lower_difficulty,
                            ))
                            if lower_location_id is not None:
                                await self._send_location_check_once(ctx, lower_location_id)

            self.snapshot_stage = None
            self.snapshot_char = None
            self.snapshot_difficulty = None

        # Break the Targets uses a different state and character byte.
        # Confirmed values: state 0x35 while in BTT, 0x0A4B09 stores the selected character.
        slot_data = getattr(ctx, "slot_data", None) or {}
        include_bonus_stages = bool(slot_data.get("include_bonus_stages", True))
        if include_bonus_stages:
            if game_state == STATE_BTT:
                btt_char_id = await self._force_btt_character_from_last_classic_fight(ctx, btt_char_id)

                if self.prev_game_state != STATE_BTT:
                    self.snapshot_btt_char = btt_char_id
                elif self.snapshot_btt_char is None:
                    self.snapshot_btt_char = btt_char_id

            # When BTT ends/leaves state 0x35, award the character's Break the Targets check.
            # This currently means the bonus stage was reached/finished, not necessarily every target was broken.
            if self.prev_game_state == STATE_BTT and game_state != STATE_BTT:
                if self.snapshot_btt_char is not None and self.snapshot_btt_char in self.get_enabled_character_values(ctx):
                    location_id = location_id_by_btt_character_id.get(self.snapshot_btt_char)
                    if location_id is not None:
                        await self._send_location_check_once(ctx, location_id)
                self.snapshot_btt_char = None
        else:
            self.snapshot_btt_char = None

        self.prev_game_state = game_state

        await self.check_goal(ctx)

    async def check_goal(self, ctx: "BizHawkClientContext") -> None:
        if self.goal_sent:
            return

        slot_data = getattr(ctx, "slot_data", None) or {}
        required = int(slot_data.get("required_classic_completions", 8))
        goal_difficulty = int(slot_data.get("goal_difficulty", 0))

        checked = set(getattr(ctx, "checked_locations", set()))
        checked.update(getattr(ctx, "locations_checked", set()))
        checked.update(self.local_checked_locations)

        goal_master_hand_ids = master_hand_location_ids_by_difficulty.get(goal_difficulty, master_hand_location_ids)
        total_master_hand_clears = len(master_hand_location_ids.intersection(checked))
        has_goal_difficulty_clear = bool(goal_master_hand_ids.intersection(checked))
        if total_master_hand_clears >= required and has_goal_difficulty_clear:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            self.goal_sent = True

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        try:
            # Keep all characters visible in the base game so AP can control access.
            await bizhawk.write(ctx.bizhawk_ctx, [
                (UNLOCK_ALL_CHARACTERS_ADDR, UNLOCK_ALL_CHARACTERS_VALUE, "RDRAM"),
            ])

            install_smash64_command_processor(ctx)
            await self.handle_progressive_difficulty(ctx)
            # Sync EnergyLink/SharedDamage tags before any clear/damage logic tries
            # to deposit or bounce packets on this watcher tick.
            await self.handle_energy_link(ctx)
            await self.handle_damage_link(ctx)
            await self.handle_classic_stage_checks(ctx)
            await self.handle_health_effect_items(ctx)
            await self.handle_progressive_max_stocks(ctx)
            await self.handle_death_link(ctx)
            await self.enforce_character_locks(ctx)
        except bizhawk.RequestFailedError:
            pass
