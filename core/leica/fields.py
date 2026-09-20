"""Authoritative Leica Look property definitions from v1.2."""

FIELD_ORDER = (0xD861, 0xDC44, 0xDC86, 0xD860, 0xD864, 0xD866)
FIELD_NAMES = {
    0xD861: "look_id",
    0xDC44: "name",
    0xDC86: "icon",
    0xD860: "cube",
    0xD864: "type",
    0xD866: "base",
}
FIELD_TYPES = {
    0xD861: 0x0006,
    0xDC44: 0xFFFF,
    0xDC86: 0x4002,
    0xD860: 0x4002,
    0xD864: 0x0006,
    0xD866: 0x0006,
}
AUTHORITATIVE_D864 = 2
AUTHORITATIVE_BASES = {0: "Standard", 1: "Monochrome"}
DEFAULT_MARKER = 0x20000014