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
        # Isolated renderer tests do not run the palette scan first. Give their
        # tree trunks a valid fixture slot; allocator tests replace it normally.
        self.put('wTreeTrunkPalette', 6)
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

    def test_all_ten_distinct_allocations_and_bank1_pose_split(self):
        m = self.m
        for index in range(1, 11):
            self.assertFalse(m.spawn(index, index + 6)['F'] & 0x10)
        self.assertEqual([m.tile(i) for i in range(1, 11)], [0x8c, 0x98, 0xa4, 0xb0, 0xbc, 0xc8, 0xd4, 0, 12, 24])
        entries = m.draw(8, 1)
        self.assertEqual([e[2] for e in entries], list(range(0x40, 0x44)))
        self.assertTrue(all(e[3] & 8 for e in entries))
        self.assertEqual(m.vram(0, 0x8600, 0x8800), bytes([0xa5]) * 0x200)
        self.assertEqual(m.vram(0, 0x8e00, 0x9000), bytes([0xa5]) * 0x200)
        self.assertEqual(m.vram(1, 0x8800, 0x9000), bytes([0x5a]) * 0x800)

    def test_exhausted_shared_slots_reject_new_resource_but_allow_duplicates(self):
        m = self.m
        for i in range(1, 11):
            self.assertFalse(m.spawn(i, i + 6)['F'] & 0x10)
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        self.assertTrue(m.spawn(11, 17)['F'] & 0x10)
        self.assertEqual(m.tile(11), 0xff)
        self.assertEqual(m.draw(11, 0), [])
        self.assertEqual([m.vram(b, 0x8000, 0x9000) for b in (0, 1)], before)
        self.assertFalse(m.spawn(12, 7)['F'] & 0x10)
        self.assertEqual(m.tile(12), m.tile(1))
        self.assertTrue(m.spawn(11, 'SPRITE_BIG_GYARADOS')['F'] & 0x10)
        self.assertEqual([m.vram(b, 0x8000, 0x9000) for b in (0, 1)], before)
        m.remove(2)
        self.assertFalse(m.spawn(11, 'SPRITE_BIG_GYARADOS')['F'] & 0x10)
        self.assertEqual(m.tile(11), 0x18)
        self.assertEqual(m.tile(10), 0x98)  # ordinary owner moved out of slot 9

    def test_full_allocator_map_spawn_does_not_publish_failed_object(self):
        m = self.m
        for i in range(1, 11):
            m.spawn(i, i + 6)
        m.remove(11)  # match the engine's initialized empty-object state
        ptr = m.addr('wMapObjects') + 11 * 14
        m.p.memory[ptr:ptr + 14] = [255, 17, 5, 5, 1, 0, 0, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 11)
        m.put('hMapObjectIndexBuffer', 11)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(11))
        self.assertTrue(out['F'] & 0x10)
        self.assertEqual(m.p.memory[ptr], 255)
        self.assertEqual(m.p.memory[m.obj(11)], 0)
        self.assertEqual(m.p.memory[m.obj(11) + 1], 255)

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
        m.spawn(3, 'SPRITE_TEACHER')
        # A real font load overwrites the alternate bank-0 area.
        m.call('_LoadStandardFont')
        self.assertNotEqual(m.graphics(1), self.expected('youngster'))
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(len(m.loads), 3)
        self.assertEqual(m.tile(1), m.tile(2))
        self.assertEqual(m.graphics(1), self.expected('youngster'))
        self.assertEqual(m.graphics(3), self.expected('teacher'))
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
        self.assertEqual([m.tile(1), m.tile(2)], [0x18, 0x18])
        self.assertEqual(len(m.loads), 1)
        original = m.graphics(1)
        m.call('_LoadStandardFont')
        self.assertEqual(m.graphics(1), original)
        self.assertEqual(original, self.expected('sailboat'))

    def test_special_relocates_last_slot_and_every_shared_user(self):
        m = self.m
        for i in range(1, 11):
            m.spawn(i, i + 6)
        last_sprite = m.p.memory[m.obj(10)]
        last_gfx = m.graphics(10)
        m.remove(1)
        m.spawn(1, last_sprite)  # now objects 1 and 10 share final allocation
        m.remove(2)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(m.tile(2), 0x18)
        self.assertEqual(m.tile(1), m.tile(10))
        self.assertNotEqual(m.tile(1), 0x18)
        self.assertEqual(m.graphics(1), last_gfx)
        self.assertEqual(m.graphics(2, 15), self.expected('big_gyarados', 15))
        self.assertEqual(m.vram(1, 0x83f0, 0x8400), bytes([0x5a]) * 16)
        self.assertEqual(m.vram(1, 0x87f0, 0x8800), bytes([0x5a]) * 16)

    def test_relocation_publishes_oam_before_reusing_old_tiles(self):
        m = self.m
        for i in range(1, 11):
            m.spawn(i, i + 6)
        last_sprite = m.p.memory[m.obj(10)]
        m.remove(1)
        m.spawn(1, last_sprite)
        for i in range(2, 10):
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
        self.assertEqual(m.tile(1), m.tile(10))
        self.assertEqual(m.tile(2), 0x18)
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)

    def test_special_sprite_exact_new_ranges_and_freed_space(self):
        m = self.m
        transfers = []
        def on_copy(_):
            f = m.p.register_file
            transfers.append((f.HL, f.C))
        m.p.hook_register(*SYMBOLS['LoadUsedSpriteGFX.CopyToVram'], on_copy, None)
        for sprite, file, count in (('SPRITE_BIG_GYARADOS', 'big_gyarados', 15),
                                    ('SPRITE_ALOLAN_EXEGGUTOR', 'alolan_exeggutor', 15),
                                    ('SPRITE_SAILBOAT', 'sailboat', 12)):
            with self.subTest(sprite=sprite):
                m.remove(1)
                m.fill_vram(1, 0x8000, 0x9000, 0x5a)
                transfers.clear()
                self.assertFalse(m.spawn(1, sprite)['F'] & 0x10)
                self.assertEqual(transfers, [(0x8180, count), (0x8580, count)])
                self.assertEqual(m.tile(1), 0x18)
                base, alternate = self.expected(file, count)
                expected = bytearray([0x5a] * 0x1000)
                expected[0x180:0x180 + count * 16] = base
                # Exeggutor's existing 24-tile sheet is shorter than its 30-tile
                # upload. Check its valid source pixels and exact write bounds;
                # the six trailing scratch tiles remain outside this layout change.
                actual_alternate = m.vram(1, 0x8580, 0x8580 + count * 16)
                self.assertEqual(actual_alternate[:len(alternate)], alternate)
                expected[0x580:0x580 + count * 16] = actual_alternate
                self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes(expected))
                self.assertEqual(m.vram(0, 0x8000, 0x9000), bytes([0xa5]) * 0x1000)

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

    def test_chris_vertical_steps_keep_head_unflipped_in_every_state(self):
        m = self.m
        down = [(12, 8, 0x80, 0), (12, 16, 0x81, 0),
                (20, 16, 0x82, 0x20), (20, 8, 0x83, 0x20)]
        up = [(12, 8, 0x84, 0), (12, 16, 0x85, 0),
              (20, 16, 0x86, 0x20), (20, 8, 0x87, 0x20)]
        for sprite in ('SPRITE_CHRIS', 'SPRITE_CHRIS_RUN',
                       'SPRITE_CHRIS_BIKE', 'SPRITE_CHRIS_SURF'):
            with self.subTest(sprite=sprite):
                m.spawn(0, sprite)
                down_entries = m.draw(0, 3)
                up_entries = m.draw(0, 7)
                self.assertEqual(down_entries[:4], down)
                self.assertEqual(up_entries[:4], up)
                expected_count = 7 if sprite == 'SPRITE_CHRIS' else 4
                self.assertEqual((len(down_entries), len(up_entries)),
                                 (expected_count, 6 if sprite == 'SPRITE_CHRIS' else 4))

        # Other player characters, and NPCs borrowing Chris's sprite, retain
        # the generic whole-body mirror.
        m.spawn(0, 'SPRITE_KRIS')
        generic = [(12, 16, 0x80, 0x20), (12, 8, 0x81, 0x20),
                   (20, 16, 0x82, 0x20), (20, 8, 0x83, 0x20)]
        self.assertEqual(m.draw(0, 3), generic)
        m.spawn(1, 'SPRITE_CHRIS')
        npc = m.draw(1, 3)
        self.assertEqual([(entry[1], entry[3] & 0x20) for entry in npc],
                         [(16, 0x20), (8, 0x20), (16, 0x20), (8, 0x20)])

    def test_regular_chris_overlay_all_walk_facings_use_bank1_palette_and_offsets(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        m.call('CheckForUsedObjPals')
        slot = 1
        self.assertEqual(m.p.memory[m.addr('wLoadedObjPal0')], 0)
        self.assertEqual(m.p.memory[m.addr('wLoadedObjPal0') + slot], 0x1c)

        # Coordinates are relative to the player's (y=12, x=8) render origin.
        # Right-facing records reflect both the tile and its horizontal offset.
        down_static = [(0, 0, 0x74, 0), (0, 8, 0x75, 0), (8, 4, 0x76, 0)]
        down_walk = [(1, 0, 0x74, 0), (1, 8, 0x75, 0), (9, 4, 0x7c, 0)]
        down_walk_flip = [(1, 0, 0x74, 0), (1, 8, 0x75, 0), (9, 4, 0x7c, 0x20)]
        up_static = [(-1, 4, 0x77, 0), (8, 4, 0x78, 0)]
        up_walk = [(0, 4, 0x77, 0), (8, 4, 0x7d, 0)]
        left_static = [(0, 0, 0x79, 0), (0, 8, 0x7a, 0), (8, 7, 0x7b, 0)]
        right_static = [(0, 8, 0x79, 0x20), (0, 0, 0x7a, 0x20),
                        (8, 1, 0x7b, 0x20)]
        left_walk = [(1, 0, 0x7e, 0), (1, 8, 0x7a, 0), (9, 5, 0x7f, 0)]
        right_walk = [(1, 8, 0x7e, 0x20), (1, 0, 0x7a, 0x20),
                      (9, 3, 0x7f, 0x20)]
        expected = {
            0: down_static, 1: down_walk, 2: down_static, 3: down_walk_flip,
            4: up_static, 5: up_walk, 6: up_static, 7: up_walk,
            8: left_static, 9: left_walk, 10: left_static, 11: left_walk,
            12: right_static, 13: right_walk, 14: right_static, 15: right_walk,
        }
        for facing, relative in expected.items():
            with self.subTest(facing=facing):
                entries = m.draw(0, facing)
                overlay = [(12 + y, 8 + x, tile, 8 | slot | flip)
                           for y, x, tile, flip in relative]
                self.assertEqual(entries[4:], overlay)
                self.assertEqual(m.p.memory[m.addr('wPlayerCurrentOAMCount')],
                                 4 + len(overlay))

    def test_chris_overlay_is_regular_state_only_and_never_partial(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        m.call('CheckForUsedObjPals')
        self.assertEqual(len(m.draw(0, 0)), 7)

        for sprite in ('SPRITE_CHRIS_RUN', 'SPRITE_CHRIS_BIKE', 'SPRITE_CHRIS_SURF'):
            with self.subTest(sprite=sprite):
                m.spawn(0, sprite)
                m.call('CheckForUsedObjPals')
                self.assertEqual(m.p.memory[m.addr('wLoadedObjPal1')], 0x1c)
                self.assertEqual(len(m.draw(0, 0)), 4)

        # An NPC using Chris's graphics never receives player overlay objects.
        m.spawn(0, 'SPRITE_CHRIS')
        m.spawn(1, 'SPRITE_CHRIS')
        m.call('CheckForUsedObjPals')
        self.assertEqual(len(m.draw(1, 0)), 4)

        # Leave exactly four OAM slots: the base player fits, but all three
        # overlay objects are rejected before any entry is written.
        m.put('hUsedOAMIndex', 36 * 4)
        shadow = m.addr('wShadowOAM')
        m.p.memory[shadow:shadow + 160] = [0] * 160
        m.call('InitSprites.InitSprite', bc=m.obj(0))
        self.assertEqual(m.p.memory[m.addr('hUsedOAMIndex')], 160)
        self.assertEqual(m.p.memory[m.addr('wPlayerCurrentOAMCount')], 4)
        tiles = m.p.memory[shadow + 2:shadow + 160:4]
        self.assertFalse(any(0x74 <= tile <= 0x7f for tile in tiles))

    def test_hide_player_sprite_hides_overlay_objects_too(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        m.call('CheckForUsedObjPals')
        self.assertEqual(len(m.draw(0, 0)), 7)
        shadow = m.addr('wShadowOAM')
        slot = m.p.memory[m.addr('wPlayerCurrentOAMSlot')]
        count = m.p.memory[m.addr('wPlayerCurrentOAMCount')]
        self.assertEqual((slot, count), (33 * 4, 7))
        m.p.memory[shadow + slot - 4] = 77
        m.call('HidePlayerSprite')
        self.assertEqual([m.p.memory[shadow + slot + i * 4] for i in range(count)],
                         [160] * count)
        self.assertEqual(m.p.memory[shadow + slot - 4], 77)

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


class DialogueRestoreTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.m.call('GetPlayerSprite')
        self.m.spawn(0, 'SPRITE_CHRIS')

    def tearDown(self):
        self.m.close()

    def capture_copies(self):
        copies = []
        def on_copy(_):
            f = self.m.p.register_file
            copies.append((f.HL, f.C))
        self.m.p.hook_register(*SYMBOLS['LoadUsedSpriteGFX.CopyToVram'], on_copy, None)
        return copies

    def test_only_live_bank0_alternates_restore_without_reallocating(self):
        m = self.m
        # Acquisition order differs from object order, reproducing the reported swap.
        m.spawn(3, 'SPRITE_TEACHER', palette=3)
        m.spawn(2, 'SPRITE_MON_ICON', species=16, form=1)
        m.spawn(1, 'SPRITE_YOUNGSTER')
        m.spawn(4, 'SPRITE_TEACHER', palette=4)
        m.spawn(5, 'SPRITE_BALL_CUT_TREE', movement=0x0c)
        m.spawn(6, 'SPRITE_BLANK_FRUIT', movement=0x21)
        m.spawn(7, 'SPRITE_BALL_CUT_TREE', movement=6)
        m.spawn(8, 'SPRITE_BIG_GYARADOS')
        objects = bytes(m.p.memory[m.obj(0):m.addr('wObjectStructsEnd')])
        keys = bytes(m.p.memory[m.addr('wSpriteGfxKeys'):m.addr('wSpriteGfxUsed')])
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        m.call('_LoadStandardFont')
        expected = bytearray(m.vram(0, 0x8000, 0x9000))
        for i in (0, 1, 3):
            start = 0x800 + (m.tile(i) & 0x7f) * 16
            expected[start:start + 192] = before[0][start:start + 192]
        copies = self.capture_copies()
        m.loads.clear()
        m.call('RestoreTextSpriteGFX')
        self.assertEqual(m.vram(0, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(1, 0x8000, 0x9000), before[1])
        self.assertEqual(copies, [(0x8800, 12), (0x88c0, 12), (0x8a40, 12)])
        self.assertEqual(len(m.loads), 3)  # player + two distinct paired resources
        self.assertEqual(bytes(m.p.memory[m.obj(0):m.addr('wObjectStructsEnd')]), objects)
        self.assertEqual(bytes(m.p.memory[m.addr('wSpriteGfxKeys'):m.addr('wSpriteGfxUsed')]), keys)

    def test_unused_keys_are_skipped_and_gaps_preserved(self):
        m = self.m
        m.spawn(1, 'SPRITE_TEACHER')
        m.spawn(2, 'SPRITE_YOUNGSTER')
        m.remove(1)
        m.call('_LoadStandardFont')
        stale = m.vram(0, 0x88c0, 0x8980)
        copies = self.capture_copies()
        m.put('hObjectStructIndexBuffer', 2)  # restore must still include object 2
        m.call('RestoreTextSpriteGFX')
        self.assertEqual(copies, [(0x8800, 12), (0x8980, 12)])
        self.assertEqual(m.tile(2), 0x98)
        self.assertEqual(m.vram(0, 0x88c0, 0x8980), stale)
        self.assertEqual(m.p.memory[m.addr('hObjectStructIndexBuffer')], 2)

    def test_all_bank0_slots_restore_once_and_bank1_is_untouched(self):
        m = self.m
        for i in range(1, 11):
            m.spawn(i, i + 6)
        old = m.vram(1, 0x8000, 0x9000)
        m.call('_LoadStandardFont')
        copies = self.capture_copies()
        m.call('RestoreTextSpriteGFX')
        self.assertEqual(copies, [(0x8800 + i * 192, 12) for i in range(8)])
        self.assertEqual(m.vram(1, 0x8000, 0x9000), old)

    def test_all_player_states_preserve_base_tiles_flags_and_banks(self):
        m = self.m
        copies = self.capture_copies()
        for gender in range(4):
            for state in range(6):
                with self.subTest(gender=gender, state=state):
                    m.put('wPlayerGender', gender)
                    m.put('wPlayerState', state)
                    m.put('wSpriteFlags', 0)
                    m.call('GetPlayerSprite')
                    m.spawn(0, m.p.memory[m.addr('wPlayerSprite')])
                    before = m.graphics(0)
                    m.call('_LoadStandardFont')
                    m.p.memory[0xff4f] = 1
                    m.put('wSpriteFlags', 0xe0)
                    bank = m.p.memory[0xff70] & 7
                    copies.clear()
                    result = m.call('RestoreTextSpriteGFX', bc=0x1234, de=0x5678, hl=0xabcd)
                    self.assertEqual((result['B'] * 256 + result['C'], result['D'] * 256 + result['E'], result['HL']),
                                     (0x1234, 0x5678, 0xabcd))
                    self.assertEqual(copies, [(0x8800, 12)])
                    self.assertEqual(m.graphics(0), before)
                    self.assertEqual(m.p.memory[m.addr('wSpriteFlags')], 0xe0)
                    self.assertEqual(m.p.memory[0xff4f] & 1, 1)
                    self.assertEqual(m.p.memory[0xff70] & 7, bank)
                    m.p.memory[0xff4f] = 0

    def setup_text_map(self):
        m = self.m
        group, number = MAPS['CHERRYGROVE_CITY']
        m.put('wMapGroup', group)
        m.put('wMapNumber', number)
        m.call('LoadMapAttributes')
        m.call('LoadMapTileset')
        m.call('GetPlayerSprite')
        m.spawn(0, 'SPRITE_CHRIS')
        m.spawn(3, 'SPRITE_TEACHER', palette=3)
        m.spawn(2, 'SPRITE_MON_ICON', species=16, form=1, palette=2)
        for i, x in ((0, 80), (2, 64), (3, 48)):
            m.p.memory[m.obj(i) + 0xb] = 1  # OBJECT_ACTION_STAND, not the hidden action 0
            m.p.memory[m.obj(i) + 0x10] = x // 16
            m.p.memory[m.obj(i) + 0x11] = 3
            m.p.memory[m.obj(i) + 0x17] = x
            m.p.memory[m.obj(i) + 0x18] = 48
        m.put('wStateFlags', 1 | 1 << 6)  # renderer enabled, text poses
        m.call('WriteOAMDMACodeToHRAM')
        checksum = m.addr('wRomChecksum')
        m.p.memory[checksum:checksum + 2] = m.p.memory[0x14e:0x150]
        m.p.memory[0xff40] = 0x93
        m.p.memory[0xffff] = 1
        m.call('SafeUpdateSprites')

    def test_real_text_open_close_never_changes_base_graphics_or_teacher_oam(self):
        m = self.m
        self.setup_text_map()
        base = m.vram(0, 0x8000, 0x8800)
        bank1 = m.vram(1, 0x8000, 0x8800)
        tiles = [m.tile(i) for i in (0, 2, 3)]
        self.assertEqual(tiles, [0x80, 0x98, 0x8c])
        samples = []
        def on_vblank_oam(_):
            entries = [tuple(m.p.memory[0xfe00 + i * 4:0xfe04 + i * 4]) for i in range(40)]
            teacher = [e for e in entries if e[0] and (e[3] & 7) == 3]
            samples.append((m.vram(0, 0x8000, 0x8800) == base,
                            all(0x0c <= e[2] <= 0x0f and not e[3] & 8 for e in teacher), len(teacher)))
        m.p.hook_register(*SYMBOLS['PushOAM'], on_vblank_oam, None)
        copies = self.capture_copies()
        for _ in range(2):
            m.call('OpenText')
            self.assertNotEqual(m.graphics(3)[1], (ROOT / 'gfx/sprites/teacher.2bpp').read_bytes()[192:384])
            copies.clear()
            m.call('Script_closetext')
            m.call('DelayFrame')
            self.assertEqual(copies, [(0x8800, 12), (0x88c0, 12)])
            self.assertEqual([m.tile(i) for i in (0, 2, 3)], tiles)
            self.assertEqual(m.vram(0, 0x8000, 0x8800), base)
            self.assertEqual(m.vram(1, 0x8000, 0x8800), bank1)
            self.assertEqual(m.graphics(3)[1], (ROOT / 'gfx/sprites/teacher.2bpp').read_bytes()[192:384])
            self.assertFalse(m.p.memory[m.addr('wStateFlags')] & (1 << 6))
        self.assertGreater(len(samples), 2)
        self.assertTrue(all(base_ok and oam_ok for base_ok, oam_ok, _ in samples))
        self.assertTrue(all(count == 4 for _, _, count in samples))
        self.assertEqual(m.p.memory[m.addr('hCrashCode')], 0)

    def test_legacy_close_text_retains_full_refresh(self):
        m = self.m
        self.setup_text_map()
        m.call('OpenText')
        copies = self.capture_copies()
        m.call('CloseText')
        self.assertTrue(any(address < 0x8800 for address, _ in copies))
        self.assertEqual(m.tile(2), 0x8c)
        self.assertEqual(m.tile(3), 0x98)
        self.assertEqual(m.graphics(3)[0], (ROOT / 'gfx/sprites/teacher.2bpp').read_bytes()[:192])

    def test_player_sprite_change_falls_back_to_full_refresh(self):
        m = self.m
        m.spawn(3, 'SPRITE_TEACHER')
        m.spawn(2, 'SPRITE_MON_ICON', species=16, form=1)
        m.put('wPlayerState', 1)  # biking changes the player graphics resource
        copies = self.capture_copies()
        m.call('RestoreTextSpriteGFX')
        self.assertTrue(any(address < 0x8800 for address, _ in copies))
        self.assertEqual(m.tile(2), 0x8c)
        self.assertEqual(m.tile(3), 0x98)
        expected_player = m.call('GetPlayerSpriteInA')['A']
        self.assertEqual(m.p.memory[m.addr('wPlayerSprite')], expected_player)


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.atlas = (ROOT / 'gfx/overworld/overworld.2bpp').read_bytes()
        self.trunks = (ROOT / 'gfx/overworld/trunks.2bpp').read_bytes()
        self.player_overlay = (ROOT / 'gfx/overlays/chris.2bpp').read_bytes()
        self.assertEqual(len(self.player_overlay), 12 * 16)
        self.outdoor_atlas = self.atlas[:9 * 16] + self.trunks + self.atlas[11 * 16:]

    def tearDown(self):
        self.m.close()

    def assert_atlas(self, expected):
        self.assertEqual(len(expected), 17 * 16)
        self.assertEqual(self.m.vram(0, 0x86f0, 0x8800), expected)
        self.assertEqual(self.m.vram(0, 0x87a0, 0x87c0),
                         (ROOT / 'gfx/overworld/fruit.2bpp').read_bytes())
        self.assertEqual(self.m.vram(1, 0x8740, 0x8800), self.player_overlay)

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
                self.assertEqual(m.vram(1, 0x8600, 0x8740), bytes([0x5a]) * 0x140)
                self.assertEqual(m.vram(1, 0x8800, 0x8900), bytes([0x5a]) * 0x100)
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
                                        (20, 12, 0x78, 0x86)])
        self.assertEqual(m.loads, [])
        self.assertEqual(m.vram(0, 0x8000, 0x8600), bytes([0xa5]) * 0x600)
        self.assertEqual(m.vram(1, 0x8000, 0x8740), bytes([0x5a]) * 0x740)
        self.assertEqual(m.vram(1, 0x8740, 0x8800), self.player_overlay)
        self.assertEqual(m.vram(0, 0x8740, 0x8780), (ROOT / 'gfx/overworld/cut_tree.2bpp').read_bytes())
        self.assertEqual(m.vram(0, 0x8780, 0x87a0), self.trunks)

    def test_cut_and_fruit_trees_share_dynamic_green_and_brown_palettes(self):
        m = self.m
        m.spawn(0, 'SPRITE_CHRIS')
        for i in (1, 2):
            m.spawn(i, 'SPRITE_BALL_CUT_TREE', movement=0x0c)
            m.p.memory[m.obj(i) + 0x21] = 0x36  # PAL_OW_COPY_BG_GREEN
            m.call('SetFacingCutTree', bc=m.obj(i))
        for i in (3, 4):
            m.spawn(i, 'SPRITE_BLANK_FRUIT', movement=0x21, species=i)
            m.call('SetFacingFruit', bc=m.obj(i))

        m.call('CheckForUsedObjPals')
        loaded = list(m.p.memory[m.addr('wLoadedObjPal0'):m.addr('wLoadedObjPal0') + 8])
        self.assertEqual(loaded[0:2], [0, 0x1c])
        self.assertEqual(loaded.count(0x36), 1)
        self.assertEqual(loaded.count(0x39), 1)  # PAL_OW_COPY_BG_BROWN
        green_slot = loaded.index(0x36)
        brown_slot = loaded.index(0x39)
        self.assertEqual(m.p.memory[m.addr('wTreeTrunkPalette')], brown_slot)
        self.assertEqual([m.p.memory[m.obj(i) + 6] & 7 for i in (1, 2)],
                         [green_slot, green_slot])
        self.assertEqual([m.draw(i)[-1][3] & 7 for i in (1, 2, 3, 4)],
                         [brown_slot] * 4)

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

    def test_blank_fruit_uses_zero_oam_and_compact_silver_cave_arch(self):
        m = self.m
        arch = (ROOT / 'gfx/overworld/silver_cave_arch.2bpp').read_bytes()
        self.assertEqual(len(arch), 32)

        for i in (1, 2):
            m.spawn(i, 'SPRITE_BLANK_FRUIT', movement=6)
            m.call('SetFacingCurrent', bc=m.obj(i))
            self.assertEqual(m.tile(i), 0x80)
            self.assertEqual(m.draw(i), [])
        self.assertEqual(m.loads, [])

        m.spawn(3, 'SPRITE_BLANK_FRUIT', movement=0x25)
        m.call('SetFacingCurrent', bc=m.obj(3))
        m.spawn(4, 'SPRITE_BLANK_FRUIT', movement=0x29)
        m.call('SetFacingMuseumDrill', bc=m.obj(4))
        self.assertEqual([m.tile(i) for i in (3, 4)], [0x3e, 0x3e])
        self.assertEqual(m.draw(3), [(12, 8, 0x3e, 8), (20, 16, 0x3f, 8)])
        self.assertEqual(m.draw(4), [(20, 16, 0x3f, 8)])
        self.assertEqual(m.graphics(3, 2)[0], arch)
        self.assertEqual(m.loads, [(*SYMBOLS['SilverCaveArchSpriteGFX'], 2)])

        m.spawn(5, 'SPRITE_BLANK_FRUIT', movement=0x21)
        self.assertEqual(m.tile(5), 0x80)
        self.assertEqual(len(m.loads), 1)

    def test_zero_oam_preserves_collision_and_emote_anchor_coordinates(self):
        m = self.m
        m.spawn(1, 'SPRITE_BLANK_FRUIT', movement=6)
        m.call('SetFacingCurrent', bc=m.obj(1))
        self.assertEqual(m.draw(1), [])
        ptr = m.obj(1)
        m.p.memory[ptr + 0x10:ptr + 0x14] = [7, 9, 7, 9]

        m.put('hMapObjectIndexBuffer', 0)
        found = m.call('IsNPCAtCoord', de=0x0709)
        self.assertTrue(found['F'] & 0x10)
        self.assertEqual(m.p.memory[m.addr('hObjectStructIndexBuffer')], 1)

        m.put('hMapObjectIndexBuffer', 1)
        m.call('SpawnEmote', bc=ptr)
        emote = m.obj(0)
        self.assertEqual(m.p.memory[emote + 3], 0x16)
        self.assertEqual(m.p.memory[emote + 0x10:emote + 0x12], [7, 9])

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
        self.assertEqual([m.tile(i) for i in (1, 2, 3, 4)], [0x80, 0x3d, 0x80, 0x3d])
        self.assertEqual(len(m.loads), 1)
        self.assertEqual(m.graphics(2, 3)[0], (ROOT / 'gfx/overworld/ball.2bpp').read_bytes())
        m.call('SetFacingCurrent', bc=m.obj(4))
        self.assertEqual([e[2] for e in m.draw(4)], [0x3d, 0x3e, 0x3f, 0x3f])
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
        self.assertEqual(m.tile(12), 0x3b)
        m.call('SetFacingCutTree', bc=m.obj(12))
        self.assertEqual(m.draw(12), [(13, 8, 0x3b, 10), (13, 16, 0x3c, 10),
                                     (21, 8, 0x3d, 10), (21, 16, 0x3e, 10),
                                     (20, 12, 0x3f, 11)])
        self.assertEqual(m.graphics(12, 5)[0],
                         (ROOT / 'gfx/overworld/faraway_rock.2bpp').read_bytes())

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


class StrengthBoulderTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.boulder = (ROOT / 'gfx/overworld/strength_boulder.2bpp').read_bytes()
        self.assertEqual(len(self.boulder), 64)

    def tearDown(self):
        self.m.close()

    def boulder_at(self, index, movement=0x13, palette=0):
        out = self.m.spawn(index, 'SPRITE_BOULDER_ROCK', movement=movement, palette=palette)
        self.assertFalse(out['F'] & 0x10)
        self.m.call('SetFacingCurrent', bc=self.m.obj(index))
        return self.m.tile(index)

    def test_pushable_and_stationary_boulders_share_four_dynamic_tiles(self):
        m = self.m
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        for i in range(1, 13):
            movement = 0x13 if i & 1 else 6
            self.assertEqual(self.boulder_at(i, movement, i % 8), 0x3c)
            self.assertEqual(m.draw(i), [(12, 8, 0x3c, 8 | i % 8),
                                         (12, 16, 0x3d, 8 | i % 8),
                                         (20, 8, 0x3e, 8 | i % 8),
                                         (20, 16, 0x3f, 8 | i % 8)])
        self.assertEqual(m.loads, [(*SYMBOLS['StrengthBoulderSpriteGFX'], 4)])
        expected = bytearray(before[1])
        expected[0x3c0:0x400] = self.boulder
        self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(0, 0x8000, 0x9000), before[0])
        m.call('MarkUsedSpriteGfx')
        self.assertEqual(m.p.memory[m.addr('wSpriteGfxUsed'):m.addr('wSpriteGfxUsed') + 10], [0] * 10)

    def test_real_map_object_and_refresh_use_one_compact_boulder_upload(self):
        m = self.m
        ptr = m.addr('wMapObjects') + 14
        m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_BOULDER_ROCK'], 5, 5,
                                    0x13, 0, 0, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(1))
        self.assertFalse(out['F'] & 0x10)
        self.assertEqual(m.tile(1), 0x3c)
        self.assertEqual(m.loads, [(*SYMBOLS['StrengthBoulderSpriteGFX'], 4)])

        m.fill_vram(1, 0x83c0, 0x8400, 0x33)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(load == (*SYMBOLS['StrengthBoulderSpriteGFX'], 4)
                             for load in m.loads), 1)
        self.assertEqual(m.tile(1), 0x3c)
        self.assertEqual(m.vram(1, 0x83c0, 0x8400), self.boulder)

    def test_pokecom_sign_and_ice_boulders_use_separate_compact_resources(self):
        m = self.m
        sign = (ROOT / 'gfx/overworld/pokecom_sign.2bpp').read_bytes()
        self.assertEqual(len(sign), 64)
        ptr = m.addr('wMapObjects') + 14
        m.p.memory[ptr:ptr + 14] = [
            255, SPRITES['SPRITE_BOULDER_ROCK'], 5, 5, 8,
            0, 0, 255, 0, 0, 0, 0, 255, 255,
        ]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(1))
        self.assertFalse(out['F'] & 0x10)
        m.call('SetFacingCurrent', bc=m.obj(1))
        m.spawn(2, 'SPRITE_BOULDER_ROCK', movement=8)
        m.call('SetFacingCurrent', bc=m.obj(2))
        m.spawn(3, 'SPRITE_ICE_BOULDER_FOSSILS', movement=0x13)
        m.call('SetFacingCurrent', bc=m.obj(3))
        self.assertEqual([m.tile(i) for i in (1, 2, 3)], [0x3c, 0x3c, 0x38])
        self.assertEqual(len(m.loads), 2)
        self.assertEqual(m.loads[0], (*SYMBOLS['PokecomSignSpriteGFX'], 4))
        self.assertEqual(m.graphics(1, 4)[0], sign)
        self.assertEqual([entry[2] for entry in m.draw(1)], [0x3c, 0x3d, 0x3e, 0x3f])
        self.assertEqual(m.graphics(3, 4)[0], (ROOT / 'gfx/overworld/ice_boulder.2bpp').read_bytes())


class IceBoulderFossilTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.close()

    def spawn(self, index, movement):
        result = self.m.spawn(index, 'SPRITE_ICE_BOULDER_FOSSILS', movement=movement)
        self.assertFalse(result['F'] & 0x10)
        self.m.call('SetFacingCurrent', bc=self.m.obj(index))
        return self.m.tile(index)

    def test_ice_boulders_and_fossils_use_exact_compact_resources(self):
        m = self.m
        resources = (
            (0x13, 'IceBoulderSpriteGFX', 'ice_boulder.2bpp'),
            (7, 'HelixFossilSpriteGFX', 'helix_fossil.2bpp'),
            (8, 'DomeFossilSpriteGFX', 'dome_fossil.2bpp'),
        )
        for index, (movement, symbol, filename) in enumerate(resources, 1):
            expected = (ROOT / 'gfx/overworld' / filename).read_bytes()
            self.assertEqual(len(expected), 64)
            self.assertEqual(self.spawn(index, movement), 0x40 - index * 4)
            self.assertEqual(m.graphics(index, 4)[0], expected)
            self.assertEqual([entry[2] for entry in m.draw(index)],
                             list(range(0x40 - index * 4, 0x44 - index * 4)))
            self.assertIn((*SYMBOLS[symbol], 4), m.loads)

        self.assertEqual(self.spawn(4, 6), 0x3c)
        self.assertEqual(len(m.loads), 3)

        m.loads.clear()
        m.call('RefreshSprites')
        for _, symbol, _ in resources:
            self.assertEqual(sum(load == (*SYMBOLS[symbol], 4)
                                 for load in m.loads), 1)
        self.assertEqual([m.tile(i) for i in range(1, 5)], [0x3c, 0x38, 0x34, 0x3c])

        source = '\n'.join(path.read_text() for path in (ROOT / 'maps').glob('*.asm'))
        movements = set(re.findall(
            r'object_event[^\n]*SPRITE_ICE_BOULDER_FOSSILS,\s*(SPRITEMOVEDATA_\w+)',
            source))
        self.assertEqual(movements, {
            'SPRITEMOVEDATA_STRENGTH_BOULDER',
            'SPRITEMOVEDATA_STANDING_DOWN',
            'SPRITEMOVEDATA_STANDING_UP',
            'SPRITEMOVEDATA_STANDING_LEFT',
        })

        for index in range(1, 5):
            m.remove(index)
        m.loads.clear()
        for index, (movement, symbol, _) in enumerate(resources, 1):
            ptr = m.addr('wMapObjects') + index * 14
            m.p.memory[ptr:ptr + 14] = [
                255, SPRITES['SPRITE_ICE_BOULDER_FOSSILS'], 5, 5, movement,
                0, 0, 255, 0, 0, 0, 0, 255, 255,
            ]
            m.put('hObjectStructIndexBuffer', index)
            m.put('hMapObjectIndexBuffer', index)
            result = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(index))
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(index), 0x40 - index * 4)
            self.assertIn((*SYMBOLS[symbol], 4), m.loads)


class CampfireTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.campfire = (ROOT / 'gfx/overworld/campfire.2bpp').read_bytes()
        self.assertEqual(len(self.campfire), 64)

    def tearDown(self):
        self.m.close()

    def test_four_tiles_reproduce_both_frames_and_deduplicate(self):
        m = self.m
        for index in range(1, 13):
            result = m.spawn(index, 'SPRITE_CAMPFIRE', movement=0x10, palette=index % 8)
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(index), 0x3c)
        self.assertEqual(m.loads, [(*SYMBOLS['CompactCampfireSpriteGFX'], 4)])
        self.assertEqual(m.graphics(1, 4)[0], self.campfire)

        ptr = m.obj(1)
        m.p.memory[ptr + 0xc] = 31
        m.call('SetFacingBounce', bc=ptr)
        self.assertEqual(m.draw(1), [
            (12, 8, 0x3c, 9), (12, 16, 0x3d, 9),
            (20, 8, 0x3e, 9), (20, 16, 0x3f, 9),
        ])

        m.p.memory[ptr + 0xc] = 15
        m.call('SetFacingBounce', bc=ptr)
        self.assertEqual(m.draw(1), [
            (12, 8, 0x3d, 0x29), (12, 16, 0x3c, 0x29),
            (20, 8, 0x3f, 0x29), (20, 16, 0x3e, 0x29),
        ])

        m.call('SetFacingFreezeBounce', bc=ptr)
        self.assertEqual([entry[2] for entry in m.draw(1)], [0x3c, 0x3d, 0x3e, 0x3f])

        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(load == (*SYMBOLS['CompactCampfireSpriteGFX'], 4)
                             for load in m.loads), 1)
        self.assertEqual([m.tile(i) for i in range(1, 13)], [0x3c] * 12)

        source = '\n'.join(path.read_text() for path in (ROOT / 'maps').glob('*.asm'))
        movements = set(re.findall(
            r'object_event[^\n]*SPRITE_CAMPFIRE,\s*(SPRITEMOVEDATA_\w+)', source))
        self.assertEqual(movements, {'SPRITEMOVEDATA_POKEMON'})

        for index in range(1, 13):
            m.remove(index)
        m.loads.clear()
        map_object = m.addr('wMapObjects') + 14
        m.p.memory[map_object:map_object + 14] = [
            255, SPRITES['SPRITE_CAMPFIRE'], 5, 5, 0x10,
            0, 0, 255, 0, 0, 0, 0, 255, 255,
        ]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        result = m.call('CopyMapObjectToObjectStruct', bc=map_object, de=m.obj(1))
        self.assertFalse(result['F'] & 0x10)
        self.assertEqual(m.tile(1), 0x3c)
        self.assertEqual(m.loads, [(*SYMBOLS['CompactCampfireSpriteGFX'], 4)])


class FloatingBallTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.floating_ball = (ROOT / 'gfx/overworld/floating_ball.2bpp').read_bytes()
        self.pokecom_news = (ROOT / 'gfx/overworld/pokecom_news.2bpp').read_bytes()
        self.assertEqual(len(self.floating_ball), 96)
        self.assertEqual(len(self.pokecom_news), 64)

    def tearDown(self):
        self.m.close()

    def test_split_resources_reproduce_animation_and_deduplicate(self):
        m = self.m
        for index in range(1, 9):
            result = m.spawn(index, 'SPRITE_FLOATING_BALL', movement=0x10, palette=1)
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(index), 0x3a)
        self.assertEqual(m.loads, [(*SYMBOLS['CompactFloatingBallSpriteGFX'], 6)])
        self.assertEqual(m.graphics(1, 6)[0], self.floating_ball)

        ptr = m.obj(1)
        m.p.memory[ptr + 0xc] = 31
        m.call('SetFacingBounce', bc=ptr)
        self.assertEqual(m.draw(1), [
            (12, 8, 0x3a, 9), (12, 16, 0x3b, 9),
            (20, 8, 0x3c, 9), (20, 16, 0x3c, 0x29),
        ])

        m.p.memory[ptr + 0xc] = 15
        m.call('SetFacingBounce', bc=ptr)
        self.assertEqual(m.draw(1), [
            (12, 8, 0x3d, 9), (12, 16, 0x3e, 9),
            (20, 8, 0x3f, 9), (20, 16, 0x3f, 0x29),
        ])

        m.call('SetFacingFreezeBounce', bc=ptr)
        self.assertEqual([entry[2] for entry in m.draw(1)],
                         [0x3a, 0x3b, 0x3c, 0x3c])

        for index in (9, 10):
            result = m.spawn(index, 'SPRITE_FLOATING_BALL', movement=0x25, palette=1)
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(index), 0x36)
            m.call('SetFacingCurrent', bc=m.obj(index))
        self.assertEqual(m.loads, [
            (*SYMBOLS['CompactFloatingBallSpriteGFX'], 6),
            (*SYMBOLS['PokecomNewsSpriteGFX'], 4),
        ])
        self.assertEqual(m.graphics(9, 4)[0], self.pokecom_news)
        self.assertEqual(m.draw(9), [
            (12, 8, 0x36, 9), (12, 16, 0x37, 9),
            (20, 8, 0x38, 9), (20, 16, 0x39, 9),
        ])

        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(load == (*SYMBOLS['CompactFloatingBallSpriteGFX'], 6)
                             for load in m.loads), 1)
        self.assertEqual(sum(load == (*SYMBOLS['PokecomNewsSpriteGFX'], 4)
                             for load in m.loads), 1)
        self.assertEqual([m.tile(i) for i in range(1, 9)], [0x3a] * 8)
        self.assertEqual([m.tile(i) for i in (9, 10)], [0x36, 0x36])

        source = '\n'.join(path.read_text() for path in (ROOT / 'maps').glob('*.asm'))
        movements = re.findall(
            r'object_event[^\n]*SPRITE_FLOATING_BALL,\s*(SPRITEMOVEDATA_\w+)', source)
        self.assertEqual(movements.count('SPRITEMOVEDATA_POKEMON'), 8)
        self.assertEqual(movements.count('SPRITEMOVEDATA_POKECOM_NEWS'), 1)
        self.assertEqual(len(movements), 9)

        for index in range(1, 11):
            m.remove(index)
        m.loads.clear()
        for index, movement, symbol, tile in (
                (1, 0x10, 'CompactFloatingBallSpriteGFX', 0x3a),
                (2, 0x25, 'PokecomNewsSpriteGFX', 0x36)):
            map_object = m.addr('wMapObjects') + index * 14
            m.p.memory[map_object:map_object + 14] = [
                255, SPRITES['SPRITE_FLOATING_BALL'], 5, 5, movement,
                0, 0, 255, 0, 0, 0, 0, 255, 255,
            ]
            m.put('hObjectStructIndexBuffer', index)
            m.put('hMapObjectIndexBuffer', index)
            result = m.call('CopyMapObjectToObjectStruct', bc=map_object, de=m.obj(index))
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(index), tile)
            self.assertIn((*SYMBOLS[symbol], 6 if movement == 0x10 else 4), m.loads)


class SmashableRockTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.rock = (ROOT / 'gfx/overworld/smashable_rock.2bpp').read_bytes()
        self.assertEqual(len(self.rock), 64)

    def tearDown(self):
        self.m.close()

    def rock_at(self, index, palette=0):
        out = self.m.spawn(index, 'SPRITE_BOULDER_ROCK', movement=0x12, palette=palette)
        self.assertFalse(out['F'] & 0x10)
        self.m.call('SetFacingCurrent', bc=self.m.obj(index))
        return self.m.tile(index)

    def test_twelve_smashable_rocks_upload_four_dynamic_tiles_once(self):
        m = self.m
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        for i in range(1, 13):
            self.assertEqual(self.rock_at(i, palette=i % 8), 0x3c)
            entries = m.draw(i)
            self.assertEqual(entries, [(12, 8, 0x3c, 8 | i % 8),
                                       (12, 16, 0x3d, 8 | i % 8),
                                       (20, 8, 0x3e, 8 | i % 8),
                                       (20, 16, 0x3f, 8 | i % 8)])
        self.assertEqual(m.loads, [(*SYMBOLS['SmashableRockSpriteGFX'], 4)])
        expected = bytearray(before[1])
        expected[0x3c0:0x400] = self.rock
        self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(0, 0x8000, 0x9000), before[0])
        m.call('MarkUsedSpriteGfx')
        self.assertEqual(m.p.memory[m.addr('wSpriteGfxUsed'):m.addr('wSpriteGfxUsed') + 10], [0] * 10)

    def test_dynamic_rock_and_ball_coexist_without_shared_allocations(self):
        m = self.m
        self.assertEqual(self.rock_at(1), 0x3c)
        m.spawn(2, 'SPRITE_BALL_CUT_TREE', movement=6)
        m.call('SetFacingCurrent', bc=m.obj(2))
        self.assertEqual(m.tile(2), 0x39)
        m.spawn(3, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(m.tile(3), 0x18)
        self.assertEqual([entry[2] for entry in m.draw(1)], [0x3c, 0x3d, 0x3e, 0x3f])
        self.assertEqual([entry[2] for entry in m.draw(2)], [0x39, 0x3a, 0x3b, 0x3b])
        self.assertEqual(m.vram(1, 0x83c0, 0x8400), self.rock)
        self.assertEqual(len(m.loads), 3)

    def test_strength_sign_and_mount_moon_rock_remain_separate(self):
        m = self.m
        m.spawn(1, 'SPRITE_BOULDER_ROCK', movement=0x13)
        m.spawn(2, 'SPRITE_BOULDER_ROCK', movement=8)
        m.call('SetFacingCurrent', bc=m.obj(2))
        m.spawn(3, 'SPRITE_N64', movement=0x12)
        m.call('SetFacingCurrent', bc=m.obj(3))
        self.assertEqual([m.tile(i) for i in (1, 2, 3)], [0x3c, 0x38, 0x34])
        self.assertEqual(len(m.loads), 3)
        self.assertEqual(m.graphics(1, 4)[0], (ROOT / 'gfx/overworld/strength_boulder.2bpp').read_bytes())
        self.assertEqual(m.graphics(2, 4)[0], (ROOT / 'gfx/overworld/pokecom_sign.2bpp').read_bytes())
        self.assertEqual(m.graphics(3, 4)[0], (ROOT / 'gfx/overworld/mount_moon_rock.2bpp').read_bytes())
        self.assertEqual([entry[2] for entry in m.draw(2)], [0x38, 0x39, 0x3a, 0x3b])
        self.assertEqual([entry[2] for entry in m.draw(3)], [0x34, 0x35, 0x36, 0x37])

    def test_real_map_object_selects_compact_rock_path(self):
        m = self.m
        ptr = m.addr('wMapObjects') + 14
        m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_BOULDER_ROCK'], 5, 5,
                                    0x12, 0, 0, 255, 0, 0, 0, 0, 255, 255]
        m.put('hObjectStructIndexBuffer', 1)
        m.put('hMapObjectIndexBuffer', 1)
        out = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(1))
        self.assertFalse(out['F'] & 0x10)
        self.assertEqual(m.tile(1), 0x3c)
        self.assertEqual(m.loads, [(*SYMBOLS['SmashableRockSpriteGFX'], 4)])

    def test_refresh_loads_live_rocks_once_and_skips_absent_rocks(self):
        m = self.m
        self.rock_at(1)
        self.rock_at(2)
        m.fill_vram(1, 0x83c0, 0x8400, 0x33)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(load == (*SYMBOLS['SmashableRockSpriteGFX'], 4)
                             for load in m.loads), 1)
        self.assertEqual([m.tile(i) for i in (1, 2)], [0x3c, 0x3c])
        self.assertEqual(m.vram(1, 0x83c0, 0x8400), self.rock)

        m.remove(1)
        m.remove(2)
        m.fill_vram(1, 0x83c0, 0x8400, 0x44)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertFalse(any(load == (*SYMBOLS['SmashableRockSpriteGFX'], 4)
                             for load in m.loads))
        self.assertEqual(m.vram(1, 0x83c0, 0x8400), bytes([0x44]) * 64)


class CompactObjectAllocatorTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.close()

    def spawn(self, index, sprite, movement):
        result = self.m.spawn(index, sprite, movement=movement)
        self.assertFalse(result['F'] & 0x10)
        self.m.call('SetFacingCurrent', bc=self.m.obj(index))
        return self.m.tile(index)

    def test_mixed_resources_pack_backward_deduplicate_and_reuse_gaps(self):
        m = self.m
        self.assertEqual(self.spawn(1, 'SPRITE_BOULDER_ROCK', 0x13), 0x3c)
        self.assertEqual(self.spawn(2, 'SPRITE_BALL_CUT_TREE', 6), 0x39)
        self.assertEqual(self.spawn(3, 'SPRITE_BOULDER_ROCK', 0x12), 0x35)
        self.assertEqual(self.spawn(4, 'SPRITE_BOULDER_ROCK', 6), 0x3c)
        self.assertEqual(self.spawn(5, 'SPRITE_BALL_CUT_TREE', 6), 0x39)
        self.assertEqual(self.spawn(6, 'SPRITE_BOULDER_ROCK', 0x12), 0x35)
        self.assertFalse(m.spawn(7, 'SPRITE_BALL_CUT_TREE', movement=0x28)['F'] & 0x10)
        self.assertFalse(m.spawn(8, 'SPRITE_BALL_CUT_TREE', movement=0x29)['F'] & 0x10)
        self.assertEqual([m.tile(i) for i in (7, 8)], [0x33, 0x33])
        self.assertEqual(len(m.loads), 4)

        m.remove(2)
        m.remove(5)
        m.loads.clear()
        self.assertEqual(self.spawn(9, 'SPRITE_BALL_CUT_TREE', 6), 0x39)
        self.assertEqual(m.loads, [(*SYMBOLS['StationaryBallSpriteGFX'], 3)])

        live = (1, 3, 4, 6, 7, 8, 9)
        before = [m.tile(i) for i in live]
        m.loads.clear()
        self.assertEqual(self.spawn(10, 'SPRITE_BIG_GYARADOS', 0x22), 0x18)
        self.assertEqual([m.tile(i) for i in live], before)
        self.assertEqual(m.loads, [(*SYMBOLS['BigGyaradosSpriteGFX'], 15)])

    def test_books_papers_and_pokedexes_use_exact_compact_resources(self):
        m = self.m
        resources = (
            (6, 'BookSpriteGFX', 'book.2bpp'),
            (7, 'PaperSpriteGFX', 'paper.2bpp'),
            (8, 'PokedexObjectSpriteGFX', 'pokedex.2bpp'),
        )
        for index, (movement, symbol, filename) in enumerate(resources, 1):
            expected = (ROOT / 'gfx/overworld' / filename).read_bytes()
            self.assertEqual(len(expected), 64)
            self.assertEqual(self.spawn(index, 'SPRITE_BOOK_PAPER_POKEDEX', movement),
                             0x40 - index * 4)
            self.assertEqual(m.graphics(index, 4)[0], expected)
            self.assertEqual(m.draw(index), [
                (12, 8, 0x40 - index * 4, 8),
                (12, 16, 0x41 - index * 4, 8),
                (20, 8, 0x42 - index * 4, 8),
                (20, 16, 0x43 - index * 4, 8),
            ])
            self.assertIn((*SYMBOLS[symbol], 4), m.loads)

        self.assertEqual(self.spawn(4, 'SPRITE_BOOK_PAPER_POKEDEX', 6), 0x3c)
        self.assertEqual(len(m.loads), 3)

        m.loads.clear()
        m.call('RefreshSprites')
        for _, symbol, _ in resources:
            self.assertEqual(sum(load == (*SYMBOLS[symbol], 4)
                                 for load in m.loads), 1)
        self.assertEqual([m.tile(i) for i in range(1, 5)], [0x3c, 0x38, 0x34, 0x3c])

        source = '\n'.join(path.read_text() for path in (ROOT / 'maps').glob('*.asm'))
        movements = set(re.findall(
            r'object_event[^\n]*SPRITE_BOOK_PAPER_POKEDEX,\s*(SPRITEMOVEDATA_\w+)',
            source))
        self.assertEqual(movements, {
            'SPRITEMOVEDATA_STANDING_DOWN',
            'SPRITEMOVEDATA_STANDING_UP',
            'SPRITEMOVEDATA_STANDING_LEFT',
        })

        for index in range(1, 5):
            m.remove(index)
        m.loads.clear()
        for index, (movement, symbol, _) in enumerate(resources, 1):
            ptr = m.addr('wMapObjects') + index * 14
            m.p.memory[ptr:ptr + 14] = [
                255, SPRITES['SPRITE_BOOK_PAPER_POKEDEX'], 5, 5, movement,
                0, 0, 255, 0, 0, 0, 0, 255, 255,
            ]
            m.put('hObjectStructIndexBuffer', index)
            m.put('hMapObjectIndexBuffer', index)
            result = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(index))
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(index), 0x40 - index * 4)
            self.assertIn((*SYMBOLS[symbol], 4), m.loads)


class SplitOverworldObjectTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.close()

    def spawn(self, index, sprite, movement, action='SetFacingCurrent', palette=0):
        out = self.m.spawn(index, sprite, movement=movement, palette=palette)
        self.assertFalse(out['F'] & 0x10)
        self.m.call(action, bc=self.m.obj(index))
        return self.m.tile(index)

    def assert_resource(self, index, symbol, filename, count):
        expected = (ROOT / 'gfx/overworld' / f'{filename}.2bpp').read_bytes()
        self.assertEqual(len(expected), count * 16)
        self.assertEqual(self.m.graphics(index, count)[0], expected)
        self.assertIn((*SYMBOLS[symbol], count), self.m.loads)

    def test_console_and_trophy_aliases_use_only_their_unique_tiles(self):
        m = self.m
        cases = (
            ('SPRITE_SNES', 'SnesConsoleSpriteGFX', 'snes', 2),
            ('SPRITE_N64', 'N64ConsoleSpriteGFX', 'n64', 4),
            ('SPRITE_GAMECUBE', 'GameCubeConsoleSpriteGFX', 'gamecube', 3),
            ('SPRITE_WII', 'WiiConsoleSpriteGFX', 'wii', 4),
            ('SPRITE_SILVER_TROPHY', 'SilverTrophyObjectSpriteGFX', 'silver_trophy', 4),
            ('SPRITE_GOLD_TROPHY', 'GoldTrophyObjectSpriteGFX', 'gold_trophy', 4),
        )
        expected_bases = (0x3e, 0x3a, 0x37, 0x33, 0x2f, 0x2b)
        for index, ((sprite, symbol, filename, count), base) in enumerate(
                zip(cases, expected_bases), 1):
            self.assertEqual(self.spawn(index, sprite, 1), base)
            self.assert_resource(index, symbol, filename, count)

        self.assertEqual([entry[2] for entry in m.draw(1)],
                         [0x3e, 0x3e, 0x3f, 0x3f])
        self.assertEqual([entry[3] & 0x20 for entry in m.draw(1)],
                         [0, 0x20, 0, 0x20])
        self.assertEqual([entry[2] for entry in m.draw(3)],
                         [0x37, 0x37, 0x38, 0x39])
        self.assertEqual([entry[3] & 0x20 for entry in m.draw(3)],
                         [0, 0x20, 0, 0])

    def test_snes_n64_and_pearl_variants_route_by_movement(self):
        m = self.m
        cases = (
            ('SPRITE_SNES', 7, 'CrystalVerticalSpriteGFX', 'crystal_vertical', 4,
             'SetFacingCurrent'),
            ('SPRITE_SNES', 8, 'CrystalHorizontalSpriteGFX', 'crystal_horizontal', 4,
             'SetFacingCurrent'),
            ('SPRITE_N64', 0x12, 'MountMoonRockSpriteGFX', 'mount_moon_rock', 4,
             'SetFacingCurrent'),
            ('SPRITE_N64', 8, 'LodestoneSpriteGFX', 'lodestone', 4,
             'SetFacingCurrent'),
            ('SPRITE_PEARL', 6, 'PearlObjectSpriteGFX', 'pearl', 4,
             'SetFacingCurrent'),
        )
        expected_bases = (0x3c, 0x38, 0x34, 0x30, 0x2c)
        for index, ((sprite, movement, symbol, filename, count, action), base) in enumerate(
                zip(cases, expected_bases), 1):
            self.assertEqual(self.spawn(index, sprite, movement, action), base)
            self.assert_resource(index, symbol, filename, count)

        for index in range(1, 6):
            m.remove(index)
        self.assertEqual(self.spawn(6, 'SPRITE_PEARL', 0x0c,
                                    'SetFacingCutTree'), 0x3b)
        self.assert_resource(6, 'FarawayRockSpriteGFX', 'faraway_rock', 5)
        self.assertEqual(self.spawn(7, 'SPRITE_PEARL', 0x28,
                                    'SetFacingMuseumDrill'), 0x39)
        self.assertEqual(self.spawn(8, 'SPRITE_PEARL', 0x29,
                                    'SetFacingMuseumDrill'), 0x39)
        self.assert_resource(7, 'VermilionArchSpriteGFX', 'vermilion_arch', 2)
        self.assertEqual([entry[2] for entry in m.draw(6)],
                         [0x3b, 0x3c, 0x3d, 0x3e, 0x3f])
        self.assertEqual(m.draw(7), [(12, 8, 0x39, 8)])
        self.assertEqual(m.draw(8), [(12, 16, 0x3a, 8)])
        self.assertEqual(sum(load == (*SYMBOLS['VermilionArchSpriteGFX'], 2)
                             for load in m.loads), 1)

    def test_weird_tree_animation_and_caitlin_share_no_duplicate_tiles(self):
        m = self.m
        self.assertEqual(self.spawn(1, 'SPRITE_WEIRD_TREE', 0x11,
                                    'SetFacingWeirdTree'), 0x39)
        self.assertEqual(self.spawn(2, 'SPRITE_WEIRD_TREE', 8), 0x37)
        self.assert_resource(1, 'CompactWeirdTreeSpriteGFX', 'weird_tree', 7)
        self.assert_resource(2, 'CaitlinBackSpriteGFX', 'caitlin_back', 2)
        expected = (
            [0x39, 0x3a, 0x3b, 0x3b],
            [0x3c, 0x3d, 0x3e, 0x3f],
            [0x39, 0x3a, 0x3b, 0x3b],
            [0x3c, 0x3d, 0x3e, 0x3f],
        )
        for facing, tiles in enumerate(expected, 0x54):
            self.assertEqual([entry[2] for entry in m.draw(1, facing)], tiles)
        self.assertEqual([entry[2] for entry in m.draw(2)],
                         [0x37, 0x37, 0x38, 0x38])

    def test_sinjoh_unown_keep_open_and_closed_eye_frames(self):
        m = self.m
        cases = (
            ('SPRITE_WII', 'UnownWSpriteGFX', 'unown_w', 4, 0x3c,
             [0, 0, 1, 1], [2, 2, 3, 3]),
            ('SPRITE_GAMECUBE', 'UnownASpriteGFX', 'unown_a', 3, 0x39,
             [0, 0, 1, 1], [2, 2, 1, 1]),
            ('SPRITE_GOLD_TROPHY', 'UnownRSpriteGFX', 'unown_r', 4, 0x35,
             [0, 0, 1, 2], [3, 3, 1, 2]),
            ('SPRITE_SILVER_TROPHY', 'UnownPSpriteGFX', 'unown_p', 8, 0x2d,
             [0, 1, 2, 3], [4, 5, 6, 7]),
        )
        for index, (sprite, symbol, filename, count, base, opened, closed) in enumerate(cases, 1):
            self.assertEqual(self.spawn(index, sprite, 0x39, 'SetFacingUnownEye'), base)
            self.assert_resource(index, symbol, filename, count)
            self.assertEqual([entry[2] for entry in m.draw(index)],
                             [base + tile for tile in opened])
            m.p.memory[m.obj(index) + 0xc] = 15
            m.call('SetFacingUnownEye', bc=m.obj(index))
            self.assertEqual([entry[2] for entry in m.draw(index)],
                             [base + tile for tile in closed])

        before = [m.tile(i) for i in range(1, 5)]
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual([m.tile(i) for i in range(1, 5)], before)
        self.assertEqual(len(m.loads), 5)  # four Unown resources plus the player
        for _, symbol, _, count, _, _, _ in cases:
            self.assertEqual(sum(load == (*SYMBOLS[symbol], count)
                                 for load in m.loads), 1)
        source = (ROOT / 'maps/RuinsOfAlphSinjohChamber.asm').read_text()
        self.assertEqual(source.count('SPRITEMOVEDATA_UNOWN_EYE'), 4)


class NamingScreenBallTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.ball = (ROOT / 'gfx/overworld/ball.2bpp').read_bytes()
        self.assertEqual(len(self.ball), 48)

    def tearDown(self):
        self.m.close()

    def test_box_icon_loads_three_tiles_and_mirrors_bottom_right(self):
        m = self.m
        m.call('NamingScreen.Box')
        self.assertEqual(m.vram(0, 0x8000, 0x8030), self.ball)
        self.assertEqual(m.vram(0, 0x8030, 0x8040), bytes([0xa5]) * 16)
        self.assertEqual(m.vram(1, 0x8000, 0x8040), bytes([0x5a]) * 64)

        for _ in range(40):
            m.call('PlaySpriteAnimations')
        oam = m.addr('wShadowOAM')
        entries = [tuple(m.p.memory[oam + i * 4:oam + i * 4 + 4]) for i in range(4)]
        self.assertEqual(entries, [(28, 24, 0, 0),
                                   (28, 32, 1, 0),
                                   (36, 24, 2, 0),
                                   (36, 32, 2, 0x20)])


class StationaryBallTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.ball = (ROOT / 'gfx/overworld/ball.2bpp').read_bytes()
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
            self.assertEqual(self.ball_at(i, palette=i % 8), 0x3d)
            entries = m.draw(i)
            self.assertEqual(entries, [(12, 8, 0x3d, 8 | i % 8),
                                       (12, 16, 0x3e, 8 | i % 8),
                                       (20, 8, 0x3f, 8 | i % 8),
                                       (20, 16, 0x3f, 0x28 | i % 8)])
        self.assertEqual(m.loads, [(*SYMBOLS['StationaryBallSpriteGFX'], 3)])
        expected = bytearray(before[1])
        expected[0x3d0:0x400] = self.ball
        self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(0, 0x8000, 0x9000), before[0])
        m.call('MarkUsedSpriteGfx')
        self.assertEqual(m.p.memory[m.addr('wSpriteGfxUsed'):m.addr('wSpriteGfxUsed') + 10], [0] * 10)

    def test_special_then_ball_only_copies_three_dynamic_bank1_tiles(self):
        m = self.m
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        before = [m.vram(b, 0x8000, 0x9000) for b in (0, 1)]
        self.assertEqual(self.ball_at(1), 0x3d)
        expected = bytearray(before[1])
        expected[0x3d0:0x400] = self.ball
        self.assertEqual(m.vram(1, 0x8000, 0x9000), bytes(expected))
        self.assertEqual(m.vram(0, 0x8000, 0x9000), before[0])
        m.spawn(3, 'SPRITE_YOUNGSTER')
        self.assertEqual(m.tile(3), 0x8c)
        self.assertEqual(m.graphics(1, 3)[0], self.ball)

    def test_special_spawn_never_moves_or_reuploads_live_balls(self):
        m = self.m
        for i in (1, 9, 12):
            self.ball_at(i, palette=i % 8)
        before = [m.draw(i) for i in (1, 9, 12)]
        m.loads.clear()
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual([m.tile(i) for i in (1, 9, 12)], [0x3d] * 3)
        self.assertEqual([m.draw(i) for i in (1, 9, 12)], before)
        self.assertEqual(m.loads, [(*SYMBOLS['BigGyaradosSpriteGFX'], 15)])
        self.assertEqual(m.graphics(1, 3)[0], self.ball)

    def test_special_relocates_ordinary_owner_without_moving_ball(self):
        m = self.m
        for i in range(1, 11):
            m.spawn(i, i + 6)
        last_graphics = m.graphics(10)
        self.ball_at(11)
        m.remove(1)
        m.loads.clear()
        m.spawn(12, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(m.tile(11), 0x3d)
        self.assertEqual(m.tile(10), 0x8c)
        self.assertEqual(m.graphics(10), last_graphics)
        self.assertEqual(m.graphics(11, 3)[0], self.ball)
        self.assertEqual(m.tile(12), 0x18)
        self.assertFalse(any(n == 3 for _, _, n in m.loads))

    def test_full_shared_capacity_still_accepts_two_balls_and_refreshes(self):
        m = self.m
        for i in range(1, 11):
            self.assertFalse(m.spawn(i, i + 6)['F'] & 0x10)
        self.assertEqual(self.ball_at(11), 0x3d)
        self.assertEqual(self.ball_at(12), 0x3d)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(len(m.loads), 12)  # player, ten resources, one ball upload
        self.assertEqual(sum(n == 3 for _, _, n in m.loads), 1)
        self.assertEqual([m.tile(i) for i in (11, 12)], [0x3d, 0x3d])
        self.assertEqual(m.graphics(11, 3)[0], self.ball)

    def test_refresh_without_balls_never_uploads_ball_tiles(self):
        m = self.m
        m.spawn(1, 'SPRITE_BIG_GYARADOS')
        m.call('RefreshSprites')
        self.assertFalse(any(n == 3 for _, _, n in m.loads))
        self.assertEqual(m.vram(1, 0x83d0, 0x8400), bytes([0x5a]) * 48)
        self.ball_at(2)
        m.remove(2)
        m.fill_vram(1, 0x83d0, 0x8400, 0x33)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertFalse(any(n == 3 for _, _, n in m.loads))
        self.assertEqual(m.vram(1, 0x83d0, 0x8400), bytes([0x33]) * 48)

    def test_map_spawn_refresh_and_deletion_do_not_load_the_old_sheet(self):
        m = self.m
        for i in (1, 2):
            ptr = m.addr('wMapObjects') + i * 14
            m.p.memory[ptr:ptr + 14] = [255, SPRITES['SPRITE_BALL_CUT_TREE'], 5, 5, 6, 0, 0, 255, 0, 0, 0, 0, 255, 255]
            m.put('hObjectStructIndexBuffer', i)
            m.put('hMapObjectIndexBuffer', i)
            result = m.call('CopyMapObjectToObjectStruct', bc=ptr, de=m.obj(i))
            self.assertFalse(result['F'] & 0x10)
            self.assertEqual(m.tile(i), 0x3d)
        self.assertEqual(len(m.loads), 1)
        m.call('_LoadStandardFont')
        m.fill_vram(1, 0x83d0, 0x8400, 0x33)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(n == 3 for _, _, n in m.loads), 1)
        self.assertEqual(m.graphics(1, 3)[0], self.ball)
        m.remove(1)
        m.loads.clear()
        self.ball_at(3)
        self.assertEqual(m.loads, [])
        m.remove(2)
        m.remove(3)
        m.fill_vram(1, 0x83d0, 0x8400, 0x55)
        self.ball_at(4)
        self.assertEqual(len(m.loads), 1)
        self.assertEqual(m.graphics(4, 3)[0], self.ball)

    def test_arch_tree_halves_share_two_tiles_and_skip_blank_oam(self):
        m = self.m
        arch_tree = (ROOT / 'gfx/overworld/arch_tree.2bpp').read_bytes()
        self.assertEqual(len(arch_tree), 32)
        self.ball_at(1)
        m.spawn(2, 'SPRITE_BALL_CUT_TREE', movement=0x28)
        m.call('SetFacingMuseumDrill', bc=m.obj(2))
        m.spawn(3, 'SPRITE_BALL_CUT_TREE', movement=0x29)
        m.call('SetFacingMuseumDrill', bc=m.obj(3))
        self.assertEqual([m.tile(i) for i in (2, 3)], [0x3b, 0x3b])
        self.assertEqual(m.draw(2), [(20, 8, 0x3b, 8)])
        self.assertEqual(m.draw(3), [(20, 16, 0x3c, 8)])
        self.assertEqual(m.graphics(2, 2)[0], arch_tree)
        self.assertEqual(sum(load == (*SYMBOLS['ArchTreeSpriteGFX'], 2)
                             for load in m.loads), 1)
        self.assertEqual(len(m.loads), 2)
        self.assertEqual(m.graphics(1, 3)[0], self.ball)

        m.fill_vram(1, 0x83b0, 0x83d0, 0x44)
        m.loads.clear()
        m.call('RefreshSprites')
        self.assertEqual(sum(load == (*SYMBOLS['ArchTreeSpriteGFX'], 2)
                             for load in m.loads), 1)
        self.assertEqual(m.graphics(2, 2)[0], arch_tree)
        self.assertEqual([m.tile(i) for i in (2, 3)], [0x3b, 0x3b])

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
        self.assertEqual(m.tile(1), 0x3d)

    def test_hardware_oam_keeps_dynamic_balls_when_special_is_loaded(self):
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

        m.call('DelayFrame')
        m.p.hook_register(*SYMBOLS['LoadSharedSpriteGfx'], check_special_load, None)
        m.spawn(2, 'SPRITE_BIG_GYARADOS')
        self.assertEqual(len(snapshots), 1)
        entries = [tuple(snapshots[0][i * 4:i * 4 + 4]) for i in range(32, 40)]
        self.assertEqual(sorted(e[2] for e in entries), sorted([0x3d, 0x3e, 0x3f, 0x3f] * 2))
        self.assertTrue(all(e[3] & 8 for e in entries))
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
