# RedPlusPlus map ports

- For every future map port or blockset change, verify boundaries between all
  affected maps that have already been ported from RedPlusPlus, in both directions.
- Shared boundary blocks must use compatible IDs and matching graphics, BG tile
  attributes (including bank, palette, flips and priority), and intended collision
  behavior in both blocksets. Sharing the same tile graphics is not sufficient:
  connection strips copy block IDs and render with the current map's blockset.
- Check the connected strips as loaded by the engine, not only each map in isolation.
  Preserve existing block meanings elsewhere when resolving a boundary conflict.
- Do not require boundary-preview compatibility between legacy/unported maps and
  newly ported maps; the legacy maps will be replaced later. Do not add compatibility
  workarounds for those boundaries unless the user explicitly requests them.
