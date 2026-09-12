#!/usr/bin/env python3
"""Run the compiled sprite routines on PyBoy's SM83 CPU and inspect VRAM/OAM.

Build first with make, then run with a Python environment containing pyboy:
    python utils/test_shared_sprite_gfx.py [path/to/rom.gbc]
The harness patches only an in-memory ROM copy with a CALL/return trap. It does
not mock the allocator, decompressor, sprite resolver, tile copier, or renderer.
No user save files are read or written. LCD-off tests make transfers synchronous.
"""
from pathlib import Path
import re
import sys
import unittest

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parents[1]
ROM = Path(sys.argv.pop(1)) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else ROOT / 'polishedcrystal-3.2.3.gbc'
SYMBOLS = {}
for line in ROM.with_suffix('.sym').read_text().splitlines():
    fields = line.split()
    if len(fields) == 2 and ':' in fields[0]:
        bank, address = fields[0].split(':')
        SYMBOLS[fields[1]] = int(bank, 16), int(address, 16)
SPRITES = {name: int(value, 16) for name, value in re.findall(
    r'const (SPRITE_\w+)\s*; ([0-9a-f]+)\b', (ROOT / 'constants/sprite_constants.asm').read_text())}
OBJECT_LENGTH = SYMBOLS['wObject1Struct'][1] - SYMBOLS['wPlayerStruct'][1]


class Machine:
    def __init__(self):
        # Explicit empty SRAM avoids loading any .ram next to the tested ROM.
        import io
        self.p = PyBoy(str(ROM), window='null', sound_emulated=False,
                       ram_file=io.BytesIO(bytes(0x8000)), log_level='ERROR')
        self.p.set_emulation_speed(0)
        m = self.p.memory
        m[0xff50] = 1  # exit boot ROM
        m[0xff40] = 0  # LCD off: use the game's immediate tile transfer path
        m[0xffff] = 0  # no asynchronous interrupts during a routine invocation
        m[0xff70] = SYMBOLS['wPlayerStruct'][0]
        m[0xc000:0xe000] = [0] * 0x2000
        m[0xff80:0xffff] = [0] * 0x7f
        m[0, 0x104] = 0xc3  # return trap falls through to JP $0110
        m[0, 0x110:0x113] = [0xc3, 0x10, 1]  # idle JP after return
        self.result = None
        self.loads = []
        self.p.hook_register(0, 0x104, self.on_return, None)
        self.p.hook_register(*SYMBOLS['LoadUsedSpriteGFX'], self.on_load, None)
        self.fill_vram(0, 0x8000, 0x9000, 0xa5)
        self.fill_vram(1, 0x8000, 0x9000, 0x5a)

    def on_return(self, _):
        f = self.p.register_file
        self.result = {k: getattr(f, k) for k in ('A', 'F', 'B', 'C', 'D', 'E', 'HL', 'SP')}

    def on_load(self, _):
        f = self.p.register_file
        self.loads.append((f.B, f.D * 256 + f.E, f.C))

    def addr(self, name):
        return SYMBOLS[name][1]

    def put(self, name, value):
        self.p.memory[self.addr(name)] = value

    def obj(self, index):
        return self.addr('wPlayerStruct') + index * OBJECT_LENGTH

    def call(self, name, a=0, bc=0, de=0x1234, hl=0xabcd):
        bank, address = SYMBOLS[name]
        # Patch CALL only; the return breakpoint must retain its injected opcode.
        self.p.memory[0, 0x100:0x104] = [0xfb if self.p.memory[0xff40] & 0x80 else 0xf3, 0xcd, address & 255, address >> 8]
        self.p.memory[0, 0x105:0x107] = [0x10, 1]
        self.p.memory[0x2000] = bank or 1
        self.put('hROMBank', bank or 1)
        f = self.p.register_file
        f.A, f.B, f.C, f.D, f.E = a, bc >> 8, bc & 255, de >> 8, de & 255
        f.HL, f.SP, f.PC = hl, self.addr('wStackTop'), 0x100
        self.result = None
        for _ in range(60):
            self.p.tick(1, False, False)
            if self.result is not None:
                assert self.result['SP'] == self.addr('wStackTop'), 'unbalanced stack'
                return self.result
        raise AssertionError(f'{name} did not return; PC={f.PC:04x}')

    def spawn(self, index, sprite, species=0, form=0, palette=0):
        sprite = SPRITES[sprite] if isinstance(sprite, str) else sprite
        ptr = self.obj(index)
        self.p.memory[ptr:ptr + OBJECT_LENGTH] = [0] * OBJECT_LENGTH
        self.p.memory[ptr] = sprite
        self.p.memory[ptr + 1] = index
        self.p.memory[ptr + 2] = 0xff
        self.p.memory[ptr + 6] = palette
        self.p.memory[ptr + 0x16] = species
        self.p.memory[ptr + 0x20] = form
        self.put('hObjectStructIndexBuffer', index)
        self.put('hIsMapObject', 0)
        out = self.call('GetSpriteVTile', a=sprite, bc=ptr)
        assert (out['B'] << 8 | out['C'], out['D'] << 8 | out['E'], out['HL']) == (ptr, 0x1234, 0xabcd)
        if not out['F'] & 0x10:
            self.p.memory[ptr + 2] = out['A']
        return out

    def tile(self, index):
        return self.p.memory[self.obj(index) + 2]

    def remove(self, index):
        ptr = self.obj(index)
        self.p.memory[ptr:ptr + OBJECT_LENGTH] = [0] * OBJECT_LENGTH
        self.p.memory[ptr + 1] = 255

    def vram(self, bank, begin, end):
        previous = self.p.memory[0xff4f]
        self.p.memory[0xff4f] = bank
        data = bytes(self.p.memory[begin:end])
        self.p.memory[0xff4f] = previous
        return data

    def fill_vram(self, bank, begin, end, byte):
        previous = self.p.memory[0xff4f]
        self.p.memory[0xff4f] = bank
        self.p.memory[begin:end] = [byte] * (end - begin)
        self.p.memory[0xff4f] = previous

    def graphics(self, index, count=12):
        tile = self.tile(index)
        bank = 0 if tile & 0x80 else 1
        base = 0x8000 + (tile & 0x7f) * 16
        alternate = base + (0x800 if bank == 0 else 0x400)
        return self.vram(bank, base, base + count * 16), self.vram(bank, alternate, alternate + count * 16)

    def draw(self, index, facing=None):
        if facing is not None:
            self.p.memory[self.obj(index) + 0xd] = facing
        self.put('hUsedOAMIndex', 0)
        addr = self.addr('wShadowOAM')
        self.p.memory[addr:addr + 160] = [0] * 160
        self.call('InitSprites.InitSprite', bc=self.obj(index))
        count = self.p.memory[self.addr('hUsedOAMIndex')] // 4
        return [tuple(self.p.memory[addr + i * 4:addr + i * 4 + 4]) for i in range(39, 39 - count, -1)]

    def close(self):
        self.p.stop(save=False)


class SharedSpriteTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.close()

    def expected(self, filename, count=12):
        data = (ROOT / 'gfx/sprites' / f'{filename}.2bpp').read_bytes()
        return data[:count * 16], data[count * 16:count * 32]

    def test_duplicates_share_with_independent_directions_and_palettes(self):
        m = self.m
        for index in (1, 9, 12):
            self.assertFalse(m.spawn(index, 'SPRITE_YOUNGSTER', palette=index % 8)['F'] & 0x10)
        self.assertEqual([m.tile(i) for i in (1, 9, 12)], [0x8c] * 3)
        self.assertEqual(len(m.loads), 1)
        self.assertEqual(m.graphics(1), self.expected('youngster'))
        # Facing table: down standing = 0; down alternate = 1; up standing = 4.
        for index, facing, offsets in [(1, 0, range(4)), (9, 1, range(0x80, 0x84)), (12, 4, range(4, 8))]:
            entries = m.draw(index, facing)
            self.assertEqual([e[2] for e in entries], [0x0c + n for n in offsets])
            self.assertTrue(all((e[3] & 0xf) == index % 8 for e in entries))

    def test_deleting_original_user_keeps_shared_graphics_alive(self):
        m = self.m
        m.spawn(1, 'SPRITE_YOUNGSTER')
        m.spawn(2, 'SPRITE_YOUNGSTER')
        original = m.graphics(2)
        m.remove(1)  # exercises bulk clearing, not just DeleteMapObject
        m.spawn(1, 'SPRITE_LYRA')
        self.assertNotEqual(m.tile(1), m.tile(2))
        self.assertEqual(m.graphics(2), original)
        m.remove(2)
        m.spawn(3, 'SPRITE_MOM')
        self.assertEqual(m.tile(3), 0x8c)

    def test_all_twelve_distinct_allocations_and_bank1_pose_split(self):
        m = self.m
        for index in range(1, 13):
            self.assertFalse(m.spawn(index, index + 6)['F'] & 0x10)
        self.assertEqual([m.tile(i) for i in range(1, 13)], [0x8c, 0x98, 0xa4, 0xb0, 0xbc, 0xc8, 0xd4, 0, 12, 24, 36, 48])
        entries = m.draw(8, 1)
        self.assertEqual([e[2] for e in entries], list(range(0x40, 0x44)))
        self.assertTrue(all(e[3] & 8 for e in entries))
        self.assertEqual(m.vram(0, 0x8600, 0x8800), bytes([0xa5]) * 0x200)
        self.assertEqual(m.vram(0, 0x8e00, 0x9000), bytes([0xa5]) * 0x200)
        self.assertEqual(m.vram(1, 0x8800, 0x9000), bytes([0x5a]) * 0x800)

    def test_fruit_shares_with_independent_picked_states(self):
        m = self.m
        for i in (1, 2, 3):
            m.spawn(i, 'SPRITE_BLANK_FRUIT', species=i, palette=i)
        self.assertEqual(len(m.loads), 1)
        self.assertEqual(len({m.tile(i) for i in (1, 2, 3)}), 1)
        m.put('wFruitTreeFlags', 1 << 2)  # only object 2 is picked
        for i in (1, 2, 3):
            m.call('SetFacingFruit', bc=m.obj(i))
        self.assertEqual(len(m.draw(1)), 2)
        self.assertEqual(len(m.draw(2)), 1)
        self.assertEqual(len(m.draw(3)), 2)
        self.assertEqual(m.graphics(1)[0], self.expected('blank_fruit')[0])

    def test_refresh_restores_overwritten_tiles_once_per_resource(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        m.spawn(1, 'SPRITE_YOUNGSTER')
        m.spawn(2, 'SPRITE_YOUNGSTER')
        m.spawn(3, 'SPRITE_BLANK_FRUIT')
        # A real font load overwrites the alternate bank-0 area.
        m.call('_LoadStandardFont')
        self.assertNotEqual(m.graphics(1), self.expected('youngster'))
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(len(m.loads), 3)
        self.assertEqual(m.tile(1), m.tile(2))
        self.assertEqual(m.graphics(1), self.expected('youngster'))
        self.assertEqual(m.graphics(3)[0], self.expected('blank_fruit')[0])
        self.assertEqual(m.graphics(0), self.expected('chris'))

    def test_variable_alias_rebind_does_not_change_other_users(self):
        m = self.m
        m.put('wVariableSprites', SPRITES['SPRITE_YOUNGSTER'])
        m.spawn(1, 'SPRITE_CONSOLE')
        m.spawn(2, 'SPRITE_YOUNGSTER')
        self.assertEqual(m.tile(1), m.tile(2))
        m.put('wVariableSprites', SPRITES['SPRITE_LYRA'])
        m.call('ReloadSpriteIndex')
        self.assertNotEqual(m.tile(1), m.tile(2))
        self.assertEqual(m.graphics(1), self.expected('lyra'))
        self.assertEqual(m.graphics(2), self.expected('youngster'))

    def test_icons_use_resolved_species_and_forms(self):
        m = self.m
        m.spawn(1, 'SPRITE_MON_ICON', species=25)
        m.spawn(2, 'SPRITE_AQUARIUM_MON', species=25, palette=4)
        m.spawn(3, 'SPRITE_MON_ICON', species=1)
        self.assertEqual(m.tile(1), m.tile(2))
        self.assertNotEqual(m.tile(1), m.tile(3))
        self.assertEqual(len(m.loads), 2)
        self.assertEqual(m.graphics(1, 8)[1], bytes([0xa5]) * 128)
        # Unown A/B have distinct icon graphics.
        m.spawn(4, 'SPRITE_MON_ICON', species=201, form=1)
        m.spawn(5, 'SPRITE_MON_ICON', species=201, form=2)
        self.assertNotEqual(m.tile(4), m.tile(5))

    def test_special_shares_and_is_safe_during_font_loading(self):
        m = self.m
        m.spawn(1, 'SPRITE_SAILBOAT')
        m.spawn(2, 'SPRITE_SAILBOAT')
        self.assertEqual([m.tile(1), m.tile(2)], [0x30, 0x30])
        self.assertEqual(len(m.loads), 1)
        original = m.graphics(1)
        m.call('_LoadStandardFont')
        self.assertEqual(m.graphics(1), original)
        self.assertEqual(original, self.expected('sailboat'))

    def test_special_relocates_last_slot_and_every_shared_user(self):
        m = self.m
        for i in range(1, 13):
            m.spawn(i, i + 6)
        last_sprite = m.p.memory[m.obj(12)]
        last_gfx = m.graphics(12)
        m.remove(1)
        m.spawn(1, last_sprite)  # now objects 1 and 12 share final allocation
        m.remove(2)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(m.tile(2), 0x30)
        self.assertEqual(m.tile(1), m.tile(12))
        self.assertNotEqual(m.tile(1), 0x30)
        self.assertEqual(m.graphics(1), last_gfx)
        self.assertEqual(m.graphics(2, 15), self.expected('big_gyarados', 15))
        self.assertEqual(m.vram(1, 0x83f0, 0x8400), bytes([0x5a]) * 16)
        self.assertEqual(m.vram(1, 0x87f0, 0x8800), bytes([0x5a]) * 16)

    def test_relocation_publishes_oam_before_reusing_old_tiles(self):
        m = self.m
        for i in range(1, 13):
            m.spawn(i, i + 6)
        last_sprite = m.p.memory[m.obj(12)]
        m.remove(1)
        m.spawn(1, last_sprite)
        for i in range(2, 12):
            m.remove(i)
        m.put('wStateFlags', 1)
        m.call('WriteOAMDMACodeToHRAM')
        m.call('_UpdateSprites')
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.p.memory[0xff40] = 0x93
        m.p.memory[0xffff] = 1
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        # The real VBlank OAM DMA has already moved both prior users to bank 0.
        hardware = [tuple(m.p.memory[0xfe00 + i * 4:0xfe04 + i * 4]) for i in range(32, 40)]
        self.assertTrue(all(not e[3] & 8 for e in hardware))
        self.assertEqual(sorted(e[2] for e in hardware), sorted(list(range(12, 16)) * 2))
        self.assertEqual(m.tile(1), m.tile(12))
        self.assertEqual(m.tile(2), 0x30)
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)

    def test_failed_map_spawn_keeps_association_and_object_slot_free(self):
        m = self.m
        m.spawn(1, 'SPRITE_BIG_GYARADOS')
        m.remove(2)
        ptr = m.addr('wMapObjects') + 28
        m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_ALOLAN_EXEGGUTOR'], 5, 5, 1, 0, 0, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 2)
        m.put('hMapObjectIndexBuffer', 2)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(2))
        self.assertTrue(out['F'] & 0x10)
        self.assertEqual(m.p.memory[ptr], 255)
        self.assertEqual(m.p.memory[m.obj(2)], 0)
        self.assertEqual(m.p.memory[m.obj(2) + 1], 255)

    def test_incompatible_specials_fail_without_corrupting_live_graphics(self):
        m = self.m
        m.spawn(1, 'SPRITE_BIG_GYARADOS')
        old = m.graphics(1, 15)
        self.assertTrue(m.spawn(2, 'SPRITE_ALOLAN_EXEGGUTOR')['F'] & 0x10)
        self.assertEqual(m.graphics(1, 15), old)
        self.assertEqual(m.draw(2, 0), [])

    def test_player_is_private_and_state_reload_preserves_npcs(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        m.spawn(1, 'SPRITE_CHRIS')
        m.spawn(2, 'SPRITE_CHRIS')
        self.assertEqual(m.tile(0), 0x80)
        self.assertEqual(m.tile(1), m.tile(2))
        self.assertNotEqual(m.tile(0), m.tile(1))
        old = m.graphics(1)
        m.put('wPlayerState', 1)  # bike
        m.call('_UpdatePlayerSprite')
        self.assertEqual(m.graphics(1), old)
        self.assertNotEqual(m.graphics(0), old)

    def test_temporary_effect_does_not_own_or_reload_a_graphics_slot(self):
        m = self.m
        m.spawn(1, 'SPRITE_YOUNGSTER')
        ptr = m.obj(2)
        m.p.memory[ptr:ptr + 3] = [255, 254, 0x80]
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(len(m.loads), 2)  # player plus one NPC; no effect reload
        self.assertEqual(m.tile(2), 0x80)

    def test_map_object_context_loads_icon_before_association(self):
        m = self.m
        ptr = m.addr('wMapObjects') + 14
        # map object: unassociated, sprite, y, x, movement, species, palette,
        # time, type, form, script pointer, event flag
        m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_MON_ICON'], 5, 5, 1, 25, 0, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(1))
        self.assertFalse(out['F'] & 0x10)
        self.assertEqual(m.p.memory[ptr], 1)
        self.assertEqual(m.tile(1), 0x8c)
        m.spawn(2, 'SPRITE_MON_ICON', species=25)
        self.assertEqual(m.tile(1), m.tile(2))

    def test_lcd_on_transfers_and_bank_restoration(self):
        m = self.m
        # Use the real VBlank transfer handler, with a valid stack/checksum.
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.put('hVBlank', 6)
        m.p.memory[0xff4f] = 1
        m.p.memory[0xff40] = 0x91
        m.p.memory[0xffff] = 1
        for i in range(1, 10):
            self.assertFalse(m.spawn(i, i + 6)['F'] & 0x10)
        # First NPC is Mom; ninth is Chuck, allocated in bank 1.
        self.assertEqual(m.graphics(1), self.expected('mom'))
        self.assertEqual(m.graphics(9), self.expected('chuck'))
        self.assertEqual(m.p.memory[0xff4f] & 1, 1)
        self.assertEqual(m.p.memory[0xff70] & 7, SYMBOLS['wPlayerStruct'][0])
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)

    def test_refresh_updates_oam_when_graphics_assignments_change(self):
        m = self.m
        m.spawn(1, 'SPRITE_LYRA')
        m.spawn(2, 'SPRITE_YOUNGSTER')
        m.remove(1)
        m.put('wStateFlags', 1)
        m.call('RefreshSprites')
        self.assertEqual(m.tile(2), 0x8c)
        addr = m.addr('wShadowOAM')
        # Object 2 is rendered last, so occupies the lowest four used entries.
        used = m.p.memory[m.addr('hUsedOAMIndex')]
        entries = [m.p.memory[addr + 160 - used + i * 4 + 2] for i in range(4)]
        self.assertEqual(sorted(entries), list(range(0x0c, 0x10)))

    def test_direct_trainer_reload_rebinds_active_object(self):
        m = self.m
        m.spawn(1, 'SPRITE_YOUNGSTER')
        m.spawn(2, 'SPRITE_YOUNGSTER')
        m.p.memory[m.addr('wMapObjects') + 14] = 1
        m.call('LoadSpriteAsMapObject1', a=SPRITES['SPRITE_LYRA'])
        self.assertNotEqual(m.tile(1), m.tile(2))
        self.assertEqual(m.graphics(1), self.expected('lyra'))
        self.assertEqual(m.graphics(2), self.expected('youngster'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
