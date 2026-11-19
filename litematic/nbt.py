"""Примитивные big-endian NBT-писатели и детерминированный gzip-контейнер.

Формат: Java NBT (сетевой порядок байтов). Значения compound передаются
списком полей (name, tag_id, value); list — кортежем (elem_tag_id, items).
"""

import struct
import zlib

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


def write_byte(f, v: int) -> None:
    f.write(struct.pack(">b", v))


def write_short(f, v: int) -> None:
    f.write(struct.pack(">h", v))


def write_int(f, v: int) -> None:
    f.write(struct.pack(">i", v))


def write_long(f, v: int) -> None:
    # TAG_Long знаковый, но BlockStates пишутся беззнаковыми 64-битными значениями
    # (Java writeLong пишет те же байты) — упаковываем двухкомплементный битовый образ.
    f.write(struct.pack(">Q", v & 0xFFFFFFFFFFFFFFFF))


def write_float(f, v: float) -> None:
    f.write(struct.pack(">f", v))


def write_double(f, v: float) -> None:
    f.write(struct.pack(">d", v))


def write_string(f, s: str) -> None:
    data = s.encode("utf-8")
    f.write(struct.pack(">H", len(data)))  # длина строки — беззнаковая u16
    f.write(data)


def write_byte_array(f, data) -> None:
    write_int(f, len(data))
    f.write(bytes(data))


def write_int_array(f, values) -> None:
    write_int(f, len(values))
    for v in values:
        write_int(f, v)


def write_long_array(f, values) -> None:
    write_int(f, len(values))
    for v in values:
        write_long(f, v)


def _write_payload(f, tag_id: int, value) -> None:
    if tag_id == TAG_BYTE:
        write_byte(f, value)
    elif tag_id == TAG_SHORT:
        write_short(f, value)
    elif tag_id == TAG_INT:
        write_int(f, value)
    elif tag_id == TAG_LONG:
        write_long(f, value)
    elif tag_id == TAG_FLOAT:
        write_float(f, value)
    elif tag_id == TAG_DOUBLE:
        write_double(f, value)
    elif tag_id == TAG_STRING:
        write_string(f, value)
    elif tag_id == TAG_BYTE_ARRAY:
        write_byte_array(f, value)
    elif tag_id == TAG_INT_ARRAY:
        write_int_array(f, value)
    elif tag_id == TAG_LONG_ARRAY:
        write_long_array(f, value)
    elif tag_id == TAG_LIST:
        elem_id, items = value
        write_byte(f, elem_id)
        write_int(f, len(items))
        for item in items:
            _write_payload(f, elem_id, item)
    elif tag_id == TAG_COMPOUND:
        for name, field_id, field_value in value:
            write_byte(f, field_id)
            write_string(f, name)
            _write_payload(f, field_id, field_value)
        write_byte(f, TAG_END)
    else:
        raise ValueError(f"неизвестный id тега: {tag_id}")


def write_named_tag(f, tag_id: int, name: str, value) -> None:
    """Именованный тег: тип + имя + payload. Корень — compound с пустым именем."""
    write_byte(f, tag_id)
    write_string(f, name)
    _write_payload(f, tag_id, value)


# FLG=0, MTIME=0 (4 байта), XFL=2, OS=0xff (неизвестная ОС) — детерминизм
_GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"


def gzip_compress(data: bytes, level: int = 9) -> bytes:
    """Детерминированный gzip: одинаковый вывод на любой платформе и в любой момент.

    Python gzip.GzipFile пишет текущее время в mtime — файлы отличались бы
    байт-в-байт. Minecraft игнорирует mtime, это про воспроизводимость.
    """
    co = zlib.compressobj(level, zlib.DEFLATED, -15)
    body = co.compress(data) + co.flush()
    trailer = struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFFF)
    return _GZIP_HEADER + body + trailer
