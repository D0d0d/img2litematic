"""НЕЗАВИСИМЫЙ декодер NBT/битстрима для round-trip тестов.

Сознательно не импортирует и не дублирует код litematic/nbt.py и
litematic/writer.py: если обе стороны «договорятся» о неверном формате,
тест это не заметит — поэтому декодер написан с нуля по спецификации.
"""

import struct


class NbtReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _read(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError(f"EOF при чтении {n} байт (pos={self.pos})")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def ubyte(self) -> int:
        return self._read(1)[0]

    def ushort(self) -> int:
        return struct.unpack(">H", self._read(2))[0]

    def int(self) -> int:
        return struct.unpack(">i", self._read(4))[0]

    def long(self) -> int:
        return struct.unpack(">q", self._read(8))[0]

    def string(self) -> str:
        n = self.ushort()
        return self._read(n).decode("utf-8")

    def payload(self, tag_id: int):
        if tag_id == 1:
            return struct.unpack(">b", self._read(1))[0]
        if tag_id == 2:
            return struct.unpack(">h", self._read(2))[0]
        if tag_id == 3:
            return self.int()
        if tag_id == 4:
            return self.long()
        if tag_id == 5:
            return struct.unpack(">f", self._read(4))[0]
        if tag_id == 6:
            return struct.unpack(">d", self._read(8))[0]
        if tag_id == 7:  # byte array
            return list(self._read(self.int()))
        if tag_id == 8:
            return self.string()
        if tag_id == 9:  # list
            elem_id = self.ubyte()
            n = self.int()
            return (elem_id, [self.payload(elem_id) for _ in range(n)])
        if tag_id == 10:  # compound
            out = {}
            while True:
                t = self.ubyte()
                if t == 0:
                    return out
                name = self.string()
                out[name] = self.payload(t)
        if tag_id == 11:  # int array
            return [self.int() for _ in range(self.int())]
        if tag_id == 12:  # long array
            return [self.long() for _ in range(self.int())]
        raise ValueError(f"неизвестный id тега: {tag_id}")

    def named_tag(self):
        tag_id = self.ubyte()
        if tag_id == 0:
            return 0, "", None
        name = self.string()
        return tag_id, name, self.payload(tag_id)


def read_compound_root(data: bytes) -> dict:
    r = NbtReader(data)
    tag_id, _name, value = r.named_tag()
    assert tag_id == 10, f"корень не compound: {tag_id}"
    return value


def decode_block_states(longs, bits: int, volume: int) -> list[int]:
    """Распаковка LSB-first битстрима (независимая реализация).

    Для каждого long берём 64-битную строку в порядке LSB→MSB, склеиваем
    и режем по bits бит: элемент i занимает биты [i*bits, (i+1)*bits).
    Чанк в строке идёт LSB→MSB слева направо, поэтому перед int() его
    нужно развернуть.
    """
    s = "".join(format(l & 0xFFFFFFFFFFFFFFFF, "064b")[::-1] for l in longs)
    return [int(s[i * bits : (i + 1) * bits][::-1], 2) for i in range(volume)]
