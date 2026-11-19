"""Тесты примитивных NBT-писателей и детерминированного gzip."""

import gzip
import io

from litematic import nbt
from nbt_test_reader import NbtReader


def _write(fn) -> bytes:
    buf = io.BytesIO()
    fn(buf)
    return buf.getvalue()


class TestStrings:
    def test_ascii(self):
        data = _write(lambda f: nbt.write_string(f, "hello"))
        assert data == b"\x00\x05" + b"hello"

    def test_utf8_roundtrip(self):
        for s in ("ÄÖÜ😀", "схема", "", "a" * 65535):  # максимум NBT-строки — u16 байт
            data = _write(lambda f, s=s: nbt.write_string(f, s))
            assert NbtReader(data).string() == s


class TestNumbers:
    def test_int_boundaries(self):
        for v in (-(2**31), 2**31 - 1, 0, -1):
            data = _write(lambda f, v=v: nbt.write_int(f, v))
            assert NbtReader(data).int() == v

    def test_long_boundaries(self):
        for v in (-(2**63), 2**63 - 1, 0, -1):
            data = _write(lambda f, v=v: nbt.write_long(f, v))
            assert NbtReader(data).long() == v

    def test_short(self):
        # TAG_Short — знаковый
        for v in (0, -32768, 32767):
            data = _write(lambda f, v=v: nbt.write_short(f, v))
            assert NbtReader(data).payload(2) == v


class TestCompoundsAndLists:
    def test_compound(self):
        value = [
            ("str", nbt.TAG_STRING, "значение"),
            ("num", nbt.TAG_INT, 42),
            ("nested", nbt.TAG_COMPOUND, [("flag", nbt.TAG_BYTE, 1)]),
        ]
        data = _write(lambda f: nbt.write_named_tag(f, nbt.TAG_COMPOUND, "", value))
        tag, name, parsed = NbtReader(data).named_tag()
        assert (tag, name) == (10, "")
        assert parsed == {"str": "значение", "num": 42, "nested": {"flag": 1}}

    def test_list(self):
        data = _write(lambda f: nbt.write_named_tag(
            f, nbt.TAG_LIST, "l", (nbt.TAG_INT, [1, -2, 3])))
        tag, name, value = NbtReader(data).named_tag()
        assert (tag, name) == (9, "l")
        assert value == (3, [1, -2, 3])

    def test_empty_list_and_compound(self):
        data = _write(lambda f: nbt.write_named_tag(
            f, nbt.TAG_LIST, "e", (nbt.TAG_COMPOUND, [])))
        _, _, value = NbtReader(data).named_tag()
        assert value == (10, [])

    def test_long_array(self):
        data = _write(lambda f: nbt.write_named_tag(
            f, nbt.TAG_LONG_ARRAY, "a", [0, -1, 2**63 - 1]))
        _, _, value = NbtReader(data).named_tag()
        assert value == [0, -1, 2**63 - 1]


class TestGzip:
    def test_header_and_content(self):
        payload = b"abc" * 100
        data = nbt.gzip_compress(payload)
        assert data[:4] == b"\x1f\x8b\x08\x00"
        assert data[4:8] == b"\x00\x00\x00\x00"  # mtime = 0
        assert gzip.decompress(data) == payload

    def test_deterministic(self):
        assert nbt.gzip_compress(b"x" * 1000) == nbt.gzip_compress(b"x" * 1000)

    def test_empty(self):
        assert gzip.decompress(nbt.gzip_compress(b"")) == b""
