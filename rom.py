from __future__ import annotations

from settings import get_settings
from worlds.Files import APAutoPatchInterface
from typing import Any, Dict

SMASH64_US_HASH = "f7c52568a31aadf26e14dc2b6416b2ed"
SMASH64_AP_MARKER_OFFSET = 0xFFBFD0
SMASH64_AP_MARKER = b"SM64AP000001"
SMASH64_PLAYER_NAME_OFFSET = SMASH64_AP_MARKER_OFFSET + len(SMASH64_AP_MARKER)
SMASH64_PLAYER_NAME_LENGTH = 64

# N64 ROM byte-order headers.
# .z64 = big-endian/native:      80 37 12 40
# .v64 = byteswapped 16-bit:     37 80 40 12
# .n64 = little-endian 32-bit:   40 12 37 80
N64_Z64_MAGIC = b"\x80\x37\x12\x40"
N64_V64_MAGIC = b"\x37\x80\x40\x12"
N64_N64_MAGIC = b"\x40\x12\x37\x80"


def _byteswap_v64_to_z64(data: bytes) -> bytes:
    """Convert a .v64/16-bit-byteswapped N64 ROM to .z64 byte order."""
    if len(data) % 2 != 0:
        raise ValueError("Invalid .v64 ROM: file size is not divisible by 2.")

    rom = bytearray(data)
    for i in range(0, len(rom), 2):
        rom[i], rom[i + 1] = rom[i + 1], rom[i]
    return bytes(rom)


def _byteswap_n64_to_z64(data: bytes) -> bytes:
    """Convert a .n64/little-endian N64 ROM to .z64 byte order."""
    if len(data) % 4 != 0:
        raise ValueError("Invalid .n64 ROM: file size is not divisible by 4.")

    rom = bytearray(data)
    for i in range(0, len(rom), 4):
        rom[i:i + 4] = reversed(rom[i:i + 4])
    return bytes(rom)


def normalize_n64_rom_to_z64(data: bytes) -> bytes:
    """Return ROM data in .z64 byte order, accepting .z64, .n64, or .v64 input."""
    if len(data) < 4:
        raise ValueError("Super Smash Bros. 64 ROM is too small to read the N64 header.")

    magic = data[:4]
    if magic == N64_Z64_MAGIC:
        return data
    if magic == N64_V64_MAGIC:
        return _byteswap_v64_to_z64(data)
    if magic == N64_N64_MAGIC:
        return _byteswap_n64_to_z64(data)

    raise ValueError(
        "Unsupported Super Smash Bros. 64 ROM byte order. "
        "Use a valid USA .z64, .n64, or .v64 ROM."
    )


class Smash64Patch(APAutoPatchInterface):
    game = "Super Smash Bros. 64"
    patch_file_ending = ".apsmash64"
    # The AP output is always written in normalized .z64 byte order, even when
    # the source ROM was supplied as .n64 or .v64.
    result_file_ending = ".z64"
    # This is the md5 of the normalized USA .z64 ROM.  get_source_data() returns
    # normalized data, so equivalent .n64/.v64 inputs validate against this too.
    hashes: list[str | bytes] = [SMASH64_US_HASH]
    source_data: bytes

    @staticmethod
    def get_source_data() -> bytes:
        with open(get_settings().smash64_settings.rom_file, "rb") as infile:
            return normalize_n64_rom_to_z64(bytes(infile.read()))

    @staticmethod
    def get_source_data_with_cache() -> bytes:
        if not hasattr(Smash64Patch, "source_data"):
            Smash64Patch.source_data = Smash64Patch.get_source_data()
        return Smash64Patch.source_data


    def get_manifest(self) -> Dict[str, Any]:
        manifest = super().get_manifest()
        manifest["result_file_ending"] = self.result_file_ending
        manifest["allowed_hashes"] = self.hashes
        manifest["accepted_source_extensions"] = [".z64", ".n64", ".v64"]
        return manifest

    def patch(self, target: str) -> None:
        self.read()
        rom = bytearray(Smash64Patch.get_source_data_with_cache())

        if len(rom) <= SMASH64_PLAYER_NAME_OFFSET + SMASH64_PLAYER_NAME_LENGTH:
            raise ValueError("Super Smash Bros. 64 ROM is smaller than expected; expected the USA 16 MiB ROM.")

        # Put AP metadata in the blank 0xFF-filled space at the end of the USA ROM.
        # This avoids touching the executable/checksummed region while giving BizHawkClient
        # something reliable to validate and a player name to use for auto-auth.
        rom[SMASH64_AP_MARKER_OFFSET:SMASH64_AP_MARKER_OFFSET + len(SMASH64_AP_MARKER)] = SMASH64_AP_MARKER

        player_name = self.player_name.encode("utf-8")[:SMASH64_PLAYER_NAME_LENGTH - 1]
        name_field = player_name + b"\x00" * (SMASH64_PLAYER_NAME_LENGTH - len(player_name))
        rom[SMASH64_PLAYER_NAME_OFFSET:SMASH64_PLAYER_NAME_OFFSET + SMASH64_PLAYER_NAME_LENGTH] = name_field

        with open(target, "wb") as outfile:
            outfile.write(rom)
