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

# Actual map identifiers, independent of the healing atlas's selection table.
MAPS = {}
group = number = 0
for line in (ROOT / 'constants/map_constants.asm').read_text().splitlines():
    if re.match(r'\s*newgroup\b', line):
        group += 1
        number = 0
    match = re.match(r'\s*map_const (\w+),', line)
    if match:
        number += 1
        MAPS[match[1]] = group, number
MAP_NAMES = dict(re.findall(r'^\s*map_attributes (\w+),\s*(\w+),',
                           (ROOT / 'data/maps/attributes.asm').read_text(), re.M))
HEALING_MAPS = {MAP_NAMES[p.stem] for p in (ROOT / 'maps').glob('*.asm')
               if re.search(r'\bpc_nurse_event\b|\bjumpstd[ ,]+pokecenternurse\b|\bspecial HealMachineAnim\b', p.read_text())}


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

    def spawn(self, index, sprite, species=0, form=0, palette=0, movement=0):
        sprite = SPRITES[sprite] if isinstance(sprite, str) else sprite
        ptr = self.obj(index)
        self.p.memory[ptr:ptr + OBJECT_LENGTH] = [0] * OBJECT_LENGTH
        self.p.memory[ptr] = sprite
        self.p.memory[ptr + 1] = index
        self.p.memory[ptr + 2] = 0xff
        self.p.memory[ptr + 3] = movement
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

    def test_fruit_uses_atlas_with_independent_picked_states_and_palettes(self):
        m = self.m
        for i, fruit in ((1, 1), (2, 2), (3, 7)):
            m.spawn(i, 'SPRITE_BLANK_FRUIT', species=fruit, palette=i, movement=0x21)
            m.p.memory[m.obj(i) + 5] = 1 << 3  # IN_GRASS raises Y by 4; fruit priority stays unchanged
        self.assertEqual(m.loads, [])
        self.assertEqual([m.tile(i) for i in (1, 2, 3)], [0x80] * 3)
        m.put('wFruitTreeFlags', 1 << 2)  # only object 2 is picked
        for i in (1, 2, 3):
            m.call('SetFacingFruit', bc=m.obj(i))
        self.assertEqual(m.draw(1), [(12, 12, 0x7b, 1), (22, 12, 0x79, 6)])
        self.assertEqual(m.draw(2), [(22, 12, 0x79, 6)])
        self.assertEqual(m.draw(3), [(16, 11, 0x7a, 3), (22, 12, 0x79, 6)])
        m.put('wFruitTreeFlags', 0)  # daily regrowth changes the facing, not the pixels
        m.call('SetFacingFruit', bc=m.obj(2))
        self.assertEqual(m.draw(2), [(12, 12, 0x7b, 2), (22, 12, 0x79, 6)])
        self.assertEqual(m.vram(0, 0x8000, 0x9000), bytes([0xa5]) * 0x1000)
        self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes([0x5a]) * 0x1000)

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


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.atlas = (ROOT / 'gfx/overworld/overworld.2bpp').read_bytes()
        self.trunks = (ROOT / 'gfx/overworld/trunks.2bpp').read_bytes()
        self.outdoor_atlas = self.atlas[:9 * 16] + self.trunks + self.atlas[11 * 16:]

    def tearDown(self):
        self.m.close()

    def assert_atlas(self, expected):
        self.assertEqual(len(expected), 17 * 16)
        self.assertEqual(self.m.vram(0, 0x86f0, 0x8800), expected)
        self.assertEqual(self.m.vram(0, 0x87a0, 0x87c0),
                         (ROOT / 'gfx/overworld/fruit.2bpp').read_bytes())

    def set_map(self, name):
        group, number = MAPS[name]
        self.m.put('wMapGroup', group)
        self.m.put('wMapNumber', number)

    def test_atlas_selection_matches_every_map_and_all_healing_callers(self):
        m = self.m
        # This also catches new nurses/lab callers missing from the map table.
        for name in MAPS:
            with self.subTest(map=name):
                self.set_map(name)
                carry = bool(m.call('UsesHealingMachineGFX')['F'] & 0x10)
                self.assertEqual(carry, name in HEALING_MAPS)

    def test_map_transitions_upload_only_the_selected_pair_and_preserve_banks(self):
        m = self.m
        for name in sorted(HEALING_MAPS) + ['NEW_BARK_TOWN', 'POKECENTER_2F', 'OAKS_LAB', 'ROUTE_29']:
            with self.subTest(map=name):
                self.set_map(name)
                m.p.memory[0xff4f] = 1
                m.call('LoadOverworldGFX')
                expected = self.atlas if name in HEALING_MAPS else self.outdoor_atlas
                self.assert_atlas(expected)
                self.assertEqual(m.vram(0, 0x8600, 0x86f0), bytes([0xa5]) * 0xf0)
                self.assertEqual(m.vram(0, 0x8800, 0x8900), bytes([0xa5]) * 0x100)
                self.assertEqual(m.vram(1, 0x8600, 0x8900), bytes([0x5a]) * 0x300)
                self.assertEqual(m.p.memory[0xff4f] & 1, 1)
                self.assertEqual(m.p.memory[0xff70] & 7, SYMBOLS['wPlayerStruct'][0])

    def test_cut_trees_use_atlas_without_uploads_and_keep_oam_layout(self):
        m = self.m
        self.set_map('ROUTE_29')
        m.call('LoadOverworldGFX')
        for i in (1, 9, 12):
            out = m.spawn(i, 'SPRITE_BALL_CUT_TREE', palette=0x13, movement=0x0c)
            self.assertFalse(out['F'] & 0x10)
            self.assertEqual(m.tile(i), 0x80)
            # Relative priority applies only to the lower half/trunk, as before.
            m.p.memory[m.obj(i) + 5] = 1 << 3  # IN_GRASS
            m.call('SetFacingCutTree', bc=m.obj(i))
            self.assertEqual(m.draw(i), [(13, 8, 0x74, 3), (13, 16, 0x75, 3),
                                        (21, 8, 0x76, 0x83), (21, 16, 0x77, 0x83),
                                        (20, 12, 0x78, 0x84)])
        self.assertEqual(m.loads, [])
        self.assertEqual(m.vram(0, 0x8000, 0x8600), bytes([0xa5]) * 0x600)
        self.assertEqual(m.vram(1, 0x8000, 0x8800), bytes([0x5a]) * 0x800)
        self.assertEqual(m.vram(0, 0x8740, 0x8780), (ROOT / 'gfx/overworld/cut_tree.2bpp').read_bytes())
        self.assertEqual(m.vram(0, 0x8780, 0x87a0), self.trunks)

    def test_twelve_fruit_trees_need_no_allocation_or_sprite_upload(self):
        m = self.m
        self.set_map('ROUTE_29')
        m.call('LoadOverworldGFX')
        before = [m.vram(bank, 0x8000, 0x9000) for bank in (0, 1)]
        for i in range(1, 13):
            out = m.spawn(i, 'SPRITE_BLANK_FRUIT', movement=0x21, species=i - 1)
            self.assertFalse(out['F'] & 0x10)
            self.assertEqual(m.tile(i), 0x80)
        self.assertEqual(m.loads, [])
        self.assertEqual([m.vram(bank, 0x8000, 0x9000) for bank in (0, 1)], before)
        m.remove(1)
        m.spawn(1, 'SPRITE_YOUNGSTER')
        self.assertEqual(m.tile(1), 0x8c)  # eleven trees retain no ordinary slot
        self.assertEqual(len(m.loads), 1)

    def test_fruit_map_spawn_and_menu_refresh_use_atlas_for_both_picked_states(self):
        m = self.m
        self.set_map('ROUTE_29')
        ptr = m.addr('wMapObjects') + 14
        m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_BLANK_FRUIT'], 5, 5,
                                  0x21, 7, 3, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(1))
        self.assertFalse(out['F'] & 0x10)
        self.assertEqual(m.p.memory[ptr], 1)
        self.assertEqual(m.tile(1), 0x80)
        self.assertEqual(m.loads, [])
        for picked in (False, True):
            m.put('wFruitTreeFlags', 0x80 if picked else 0)
            m.call('SetFacingFruit', bc=m.obj(1))
            before = m.draw(1)
            self.assertEqual([entry[2] for entry in before], [0x79] if picked else [0x7a, 0x79])
            m.call('_LoadStandardFont')
            m.fill_vram(0, 0x86f0, 0x8800, 0x33)
            m.loads.clear()
            m.call('RefreshSprites')
            self.assertEqual(len(m.loads), 1)  # only the player
            self.assertEqual(m.tile(1), 0x80)
            self.assertEqual(m.draw(1), before)
            self.assert_atlas(self.outdoor_atlas)

    def test_blank_fruit_decorations_keep_their_shared_sheet_in_bank1(self):
        m = self.m
        for i in range(1, 8):
            m.spawn(i, i + 6)
        m.loads.clear()
        for i, movement in ((8, 6), (9, 0x29), (10, 0x25)):
            m.spawn(i, 'SPRITE_BLANK_FRUIT', movement=movement)
            self.assertEqual(m.tile(i), 0)  # first bank-1 block
            self.assertEqual(m.graphics(i)[0], (ROOT / 'gfx/sprites/blank_fruit.2bpp').read_bytes()[:192])
        self.assertEqual(len(m.loads), 1)
        m.spawn(11, 'SPRITE_BLANK_FRUIT', movement=0x21)
        self.assertEqual(m.tile(11), 0x80)
        self.assertEqual(len(m.loads), 1)
        self.assertEqual([entry[2] for entry in m.draw(8, facing=0)], [0, 1, 2, 3])

    def test_fruit_tree_maps_have_trunks_available(self):
        fruit_maps = {MAP_NAMES[p.stem] for p in (ROOT / 'maps').glob('*.asm')
                      if re.search(r'\bfruittree_event\b|\bSPRITEMOVEDATA_FRUIT\b', p.read_text())}
        self.assertTrue(fruit_maps)
        self.assertFalse(fruit_maps & HEALING_MAPS, 'Fruit trunks overlap healing-machine tiles')

    def test_ball_objects_still_share_resource_independently_of_trees(self):
        m = self.m
        m.spawn(1, 'SPRITE_BALL_CUT_TREE', movement=0x0c)
        m.spawn(2, 'SPRITE_BALL_CUT_TREE', movement=6)
        m.spawn(3, 'SPRITE_BALL_CUT_TREE', movement=0x0c)
        m.spawn(4, 'SPRITE_BALL_CUT_TREE', movement=6, palette=2)
        self.assertEqual([m.tile(i) for i in (1, 2, 3, 4)], [0x80, 0x3c, 0x80, 0x3c])
        self.assertEqual(len(m.loads), 1)
        self.assertEqual(m.graphics(2, 3)[0], (ROOT / 'gfx/sprites/ball.2bpp').read_bytes())
        m.call('SetFacingCurrent', bc=m.obj(4))
        self.assertEqual([e[2] for e in m.draw(4)], [0x3c, 0x3d, 0x3e, 0x3e])
        m.remove(2)
        m.remove(4)
        m.spawn(5, 'SPRITE_YOUNGSTER')
        self.assertEqual(m.tile(5), 0x8c)  # atlas trees do not retain that slot

    def test_real_map_spawn_and_refresh_restore_tree_atlas_without_ball_load(self):
        m = self.m
        self.set_map('ROUTE_29')
        ptr = m.addr('wMapObjects') + 14
        m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_BALL_CUT_TREE'], 5, 5, 0x0c, 0, 0, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(1))
        self.assertFalse(out['F'] & 0x10)
        self.assertEqual(m.p.memory[ptr], 1)
        self.assertEqual(m.tile(1), 0x80)
        self.assertEqual(m.loads, [])
        m.call('SetFacingCutTree', bc=m.obj(1))
        before = m.draw(1)
        m.call('_LoadStandardFont')
        m.fill_vram(0, 0x86f0, 0x8800, 0x33)
        m.call('RefreshSprites')
        self.assertEqual(len(m.loads), 1)  # only the private player
        self.assertEqual(m.tile(1), 0x80)
        self.assertEqual(m.draw(1), before)
        self.assert_atlas(self.outdoor_atlas)

    def test_faraway_rocks_retain_relative_tiles_even_in_vram_bank1(self):
        m = self.m
        for i in range(1, 8):
            m.spawn(i, i + 6)
        m.spawn(12, 'SPRITE_PEARL', movement=0x0c, palette=0x12)
        self.assertEqual(m.tile(12), 0)
        m.call('SetFacingCutTree', bc=m.obj(12))
        self.assertEqual(m.draw(12), [(13, 8, 4, 10), (13, 16, 5, 10),
                                     (21, 8, 6, 10), (21, 16, 7, 10), (20, 12, 8, 11)])
        self.assertEqual(m.graphics(12)[0], (ROOT / 'gfx/sprites/pearl.2bpp').read_bytes()[:192])

    def test_refresh_holds_oam_until_the_tree_atlas_is_ready(self):
        m = self.m
        self.set_map('ROUTE_29')
        m.spawn(1, 'SPRITE_BALL_CUT_TREE', movement=0x0c)
        m.call('SetFacingCutTree', bc=m.obj(1))
        m.call('WriteOAMDMACodeToHRAM')
        m.put('wStateFlags', 1)
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.p.memory[0xff40] = 0x93
        m.p.memory[0xffff] = 1
        snapshots = []

        def atlas_transfer(_):
            if m.p.register_file.HL == 0x86f0:
                snapshots.append((m.p.memory[m.addr('hOAMUpdate')],
                                  bytes(m.p.memory[0xfe00:0xfea0]),
                                  bytes(m.p.memory[m.addr('wDecompressScratch'):m.addr('wDecompressScratch') + 272])))

        m.p.hook_register(*SYMBOLS['Get2bpp'], atlas_transfer, None)
        for previous in (0, 1):
            m.p.memory[0xfe00:0xfea0] = [0] * 160
            m.put('hOAMUpdate', previous)
            m.call('RefreshSprites')
            self.assertEqual(snapshots[-1], (1, bytes(160), self.outdoor_atlas))
            self.assertEqual(m.p.memory[m.addr('hOAMUpdate')], previous)
            self.assert_atlas(self.outdoor_atlas)
        self.assertEqual(len(snapshots), 2)

    def test_lcd_on_atlas_transfers_restore_trunks_after_healing_map(self):
        m = self.m
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.put('hVBlank', 6)
        m.p.memory[0xff4f] = 1
        m.p.memory[0xff40] = 0x91
        m.p.memory[0xffff] = 1
        for name in ('ROUTE_29', 'ELMS_LAB', 'HALL_OF_FAME', 'ROUTE_29'):
            self.set_map(name)
            m.call('LoadOverworldGFX')
            expected = self.atlas if name in HEALING_MAPS else self.outdoor_atlas
            self.assert_atlas(expected)
            self.assertEqual(m.p.memory[0xff4f] & 1, 1)
            self.assertEqual(m.p.memory[0xff70] & 7, SYMBOLS['wPlayerStruct'][0])
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)


class StationaryBallTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.ball = (ROOT / 'gfx/sprites/ball.2bpp').read_bytes()
        self.assertEqual(len(self.ball), 48)

    def tearDown(self):
        self.m.close()

    def ball_at(self, index, palette=0):
        out = self.m.spawn(index, 'SPRITE_BALL_CUT_TREE', movement=6, palette=palette)
        self.assertFalse(out['F'] & 0x10)
        self.m.call('SetFacingCurrent', bc=self.m.obj(index))
        return self.m.tile(index)

    def test_twelve_balls_upload_exactly_three_tiles_and_mirror_bottom(self):
        m = self.m
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        for i in range(1, 13):
            self.assertEqual(self.ball_at(i, palette=i % 8), 0x3c)
            entries = m.draw(i)
            self.assertEqual(entries, [(12, 8, 0x3c, 8 | i % 8),
                                       (12, 16, 0x3d, 8 | i % 8),
                                       (20, 8, 0x3e, 8 | i % 8),
                                       (20, 16, 0x3e, 0x28 | i % 8)])
        self.assertEqual(m.loads, [(*SYMBOLS['StationaryBallSpriteGFX'], 3)])
        expected = bytearray(before[1])
        expected[0x3c0:0x3f0] = self.ball
        self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(0, 0x8000, 0x9000), before[0])
        m.call('MarkUsedSpriteGfx')
        self.assertEqual(m.p.memory[m.addr('wSpriteGfxUsed'):m.addr('wSpriteGfxUsed') + 12], [0] * 12)

    def test_special_then_ball_only_copies_three_tiles_in_fallback(self):
        m = self.m
        m.spawn(1, 'SPRITE_YOUNGSTER')
        m.remove(1)  # leave a stale ordinary key in block 0
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        self.assertEqual(self.ball_at(1), 0x95)
        expected = bytearray(before[0])
        expected[0x150:0x180] = self.ball
        self.assertEqual(m.vram(0, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(1, 0x8000, 0x9000), before[1])
        # The partial allocation must block overlap and must not hit a stale key.
        m.spawn(3, 'SPRITE_YOUNGSTER')
        self.assertEqual(m.tile(3), 0x98)
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        self.assertEqual(m.graphics(3)[0], (ROOT / 'gfx/sprites/youngster.2bpp').read_bytes()[:192])
        m.remove(1)
        m.spawn(4, 'SPRITE_LYRA')
        self.assertEqual(m.tile(4), 0x8c)

    def test_large_sprite_relocates_all_ball_users_without_changing_oam(self):
        m = self.m
        for i in (1, 9, 12):
            self.ball_at(i, palette=i % 8)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual([m.tile(i) for i in (1, 9, 12)], [0x95] * 3)
        for i in (1, 9, 12):
            entries = m.draw(i)
            self.assertEqual([e[2] for e in entries], [0x15, 0x16, 0x17, 0x17])
            self.assertEqual([e[3] for e in entries], [i % 8] * 3 + [0x20 | i % 8])
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        self.assertEqual(m.graphics(2, 15)[0], (ROOT / 'gfx/sprites/big_gyarados.2bpp').read_bytes()[:240])

    def test_full_population_relocates_ball_and_last_ordinary_resource(self):
        m = self.m
        for i in range(1, 13):
            m.spawn(i, i + 6)
        last_graphics = m.graphics(12)
        m.remove(1)
        m.remove(2)
        self.ball_at(1)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(m.tile(1), 0x95)
        self.assertEqual(m.tile(12), 0x98)
        self.assertEqual(m.graphics(12), last_graphics)
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        self.assertEqual(m.tile(2), 0x30)

    def test_ball_fallback_can_use_bank1_without_colliding_with_special(self):
        m = self.m
        for i in range(1, 8):
            m.spawn(i, i + 6)
        m.spawn(8, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(self.ball_at(9, palette=2), 9)
        self.assertEqual([e[3] for e in m.draw(9)], [10, 10, 10, 42])
        m.spawn(10, 'SPRITE_YOUNGSTER')
        self.assertEqual(m.tile(10), 12)
        self.assertEqual(m.graphics(9, 3)[0], self.ball)

    def test_map_spawn_refresh_and_deletion_do_not_load_the_old_sheet(self):
        m = self.m
        for i in (1, 2):
            ptr = m.addr('wMapObjects') + i * 14
            m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_BALL_CUT_TREE'], 5, 5, 6, 0, 0, 255, 0, 0, 0, 0, 255, 255]
            m.put('hObjectStructIndexBuffer', i)
            m.put('hMapObjectIndexBuffer', i)
            result = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(i))
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(i), 0x3c)
        self.assertEqual(len(m.loads), 1)
        m.call('_LoadStandardFont')
        m.fill_vram(1, 0x83c0, 0x83f0, 0x33)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(n == 3 for _, _, n in m.loads), 1)
        self.assertFalse(any((b, p) == SYMBOLS['BallCutTreeSpriteGFX'] for b, p, _ in m.loads))
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        m.remove(1)
        m.loads.clear()
        self.ball_at(3)
        self.assertEqual(m.loads, [])
        m.remove(2)
        m.remove(3)
        m.fill_vram(1, 0x83c0, 0x83f0, 0x55)
        self.ball_at(4)
        self.assertEqual(len(m.loads), 1)
        self.assertEqual(m.graphics(4, 3)[0], self.ball)

    def test_original_sheet_remains_available_to_other_object_uses(self):
        m = self.m
        self.ball_at(1)
        # Silver Cave arch-tree decoration keeps the old graphics descriptor.
        m.spawn(2, 'SPRITE_BALL_CUT_TREE', movement=0x28)
        self.assertEqual(m.tile(2), 0x8c)
        self.assertEqual(m.graphics(2)[0], (ROOT / 'gfx/sprites/ball_cut_tree.2bpp').read_bytes()[:192])
        self.assertEqual(m.graphics(1, 3)[0], self.ball)

    def test_refresh_with_large_sprite_preserves_ball_and_all_owners(self):
        m = self.m
        self.ball_at(1)
        self.ball_at(3)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        m.spawn(4, 'SPRITE_YOUNGSTER')
        m.call('_LoadStandardFont')
        m.call('RefreshSprites')
        self.assertEqual(m.tile(1), m.tile(3))
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        self.assertEqual(m.graphics(2, 15)[0], (ROOT / 'gfx/sprites/big_gyarados.2bpp').read_bytes()[:240])
        self.assertEqual(m.graphics(4)[0], (ROOT / 'gfx/sprites/youngster.2bpp').read_bytes()[:192])
        self.assertNotEqual(m.tile(1), 0x3c)

    def test_hardware_oam_moves_before_special_overwrites_ball_tail(self):
        m = self.m
        self.ball_at(1, palette=2)
        self.ball_at(3, palette=4)
        m.put('wStateFlags', 1)
        m.call('WriteOAMDMACodeToHRAM')
        m.call('_UpdateSprites')
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.p.memory[0xff40] = 0x93
        m.p.memory[0xffff] = 1
        snapshots = []

        def check_special_load(_):
            snapshots.append(bytes(m.p.memory[0xfe00:0xfea0]))

        m.p.hook_register(*SYMBOLS['LoadSharedSpriteGfx'], check_special_load, None)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(len(snapshots), 1)
        entries = [tuple(snapshots[0][i * 4:i * 4 + 4]) for i in range(32, 40)]
        self.assertEqual(sorted(e[2] for e in entries), sorted([0x15, 0x16, 0x17, 0x17] * 2))
        self.assertTrue(all(not e[3] & 8 for e in entries))
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)


class FishingRodTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.rods = (ROOT / 'gfx/overworld/fishing_rod.2bpp').read_bytes()
        self.assertEqual(len(self.rods), 32)

    def tearDown(self):
        self.m.close()

    def test_all_player_fishing_graphics_only_change_player_poses_and_scratch_rods(self):
        m = self.m
        for gender, filename in enumerate(('chris', 'kris', 'crys', 'beta')):
            for state in (0, 4, 5):
                with self.subTest(gender=gender, state=state):
                    m.put('wPlayerGender', gender)
                    m.put('wPlayerState', state)
                    m.fill_vram(0, 0x8000, 0x9000, 0xa5)
                    m.p.memory[0xff4f] = 1
                    m.call('LoadFishingGFX')
                    # Preserve the existing surf-table selection (PLAYER_SURF).
                    suffix = '_surf_fish' if state == 4 else '_fish'
                    poses = (ROOT / 'gfx/overworld' / (filename + suffix + '.2bpp')).read_bytes()
                    expected = bytearray([0xa5] * 0x1000)
                    for i, offset in enumerate((0x20, 0x60, 0xa0)):
                        expected[offset:offset + 32] = poses[i * 32:(i + 1) * 32]
                    expected[0x650:0x670] = self.rods
                    self.assertEqual(m.vram(0, 0x8000, 0x9000), bytes(expected))
                    self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes([0x5a]) * 0x1000)
                    self.assertEqual(m.p.memory[0xff4f] & 1, 1)
                    self.assertEqual(m.p.memory[0xff70] & 7, SYMBOLS['wPlayerStruct'][0])

    def test_four_fishing_directions_keep_coordinates_palette_and_flips(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS', palette=2)
        m.call('LoadFishingGFX')
        for direction, expected in [(0, (28, 8, 0x65, 2)), (4, (4, 8, 0x65, 2)),
                                    (8, (17, 0, 0x66, 0x22)), (12, (17, 24, 0x66, 2))]:
            m.p.memory[m.obj(0) + 8] = direction
            m.call('SetFacingFish', bc=m.obj(0))
            entries = m.draw(0)
            self.assertEqual(len(entries), 5)
            self.assertEqual(entries[-1], expected)
        m.call('LoadEmote', bc=0)  # shock: $60-$63 must not overwrite the rods
        self.assertEqual(m.vram(0, 0x8650, 0x8670), self.rods)

    def test_fly_graphics_and_fishing_restore_each_other(self):
        m = self.m
        m.put('wPartyCount', 1)
        m.put('wPartyMon1Species', 25)
        m.put('wPartyMon1Form', 1)
        m.put('wCurPartyMon', 0)
        m.call('FlyFunction_GetMonIcon', de=0x64)
        fly = m.vram(0, 0x8640, 0x86c0)
        m.call('LoadFishingGFX')
        self.assertEqual(m.vram(0, 0x8650, 0x8670), self.rods)
        m.call('FlyFunction_GetMonIcon', de=0x64)
        self.assertEqual(m.vram(0, 0x8640, 0x86c0), fly)
        m.call('LoadFishingGFX')
        self.assertEqual(m.vram(0, 0x8650, 0x8670), self.rods)

    def test_both_headbutt_graphics_and_fishing_restore_each_other(self):
        m = self.m
        for label, filename in [('HeadbuttTreeGFX', 'headbutt_tree'), ('HeadbuttTree2GFX', 'headbutt_tree_2')]:
            bank, source = SYMBOLS[label]
            # Execute the same decompression/transfer used at Headbutt startup.
            m.call('DecompressRequest2bpp', bc=bank * 256 + 12, de=0x8610, hl=source)
            expected = (ROOT / 'gfx/overworld' / (filename + '.2bpp')).read_bytes()
            self.assertEqual(m.vram(0, 0x8610, 0x86d0), expected)
            m.call('LoadFishingGFX')
            self.assertEqual(m.vram(0, 0x8650, 0x8670), self.rods)
            m.call('DecompressRequest2bpp', bc=bank * 256 + 12, de=0x8610, hl=source)
            self.assertEqual(m.vram(0, 0x8610, 0x86d0), expected)

    def test_lcd_on_cast_retry_and_put_away_preserve_fruit_atlas_tiles(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        normal = m.graphics(0)
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.put('hVBlank', 6)
        m.p.memory[0xff40] = 0x91
        m.p.memory[0xffff] = 1
        transfers = []

        def on_transfer(_):
            f = m.p.register_file
            if f.HL == 0x8650:
                transfers.append(f.C)

        m.p.hook_register(*SYMBOLS['Get2bpp'], on_transfer, None)
        for _ in range(2):
            m.fill_vram(0, 0x8650, 0x8670, 0x55)
            m.call('RefreshSprites')  # each cast/retry refreshes before loading
            m.p.memory[0xff4f] = 1
            m.call('LoadFishingGFX')
            self.assertEqual(m.vram(0, 0x8650, 0x8670), self.rods)
            self.assertEqual(m.p.memory[0xff4f] & 1, 1)
            self.assertEqual(m.vram(0, 0x87a0, 0x87c0), (ROOT / 'gfx/overworld/fruit.2bpp').read_bytes())
            m.call('PutTheRodAway')
            self.assertEqual(m.graphics(0), normal)
        self.assertEqual(transfers, [2, 2])
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
