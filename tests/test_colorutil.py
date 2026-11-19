"""Тесты конвертации цвета и метрик расстояния."""

import numpy as np
import pytest

from colorutil import (
    lab_dist2,
    nearest_argmin,
    redmean_dist2,
    rgb_array_to_lab,
    rgb_to_lab,
    srgb_to_linear,
)


def test_rgb_to_lab_white():
    L, a, b = rgb_to_lab((255, 255, 255))
    assert L == pytest.approx(100.0, abs=0.01)
    assert a == pytest.approx(0.0, abs=0.01)
    assert b == pytest.approx(0.0, abs=0.01)


def test_rgb_to_lab_black():
    L, _a, _b = rgb_to_lab((0, 0, 0))
    assert L == pytest.approx(0.0, abs=0.01)


def test_rgb_to_lab_red_positive_a():
    _L, a, _b = rgb_to_lab((255, 0, 0))
    assert a > 60


def test_array_matches_scalar():
    rgb = np.array([[255, 255, 255], [0, 0, 0], [255, 0, 0], [12, 34, 56]], dtype=np.uint8)
    arr = rgb_array_to_lab(rgb)
    assert arr.shape == (4, 3)
    for i in range(4):
        assert arr[i] == pytest.approx(np.array(rgb_to_lab(tuple(rgb[i]))), abs=1e-4)


def test_nearest_argmin():
    pts = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    centers = np.array([[0.0, 0.0], [10.0, 0.0]])
    assert nearest_argmin(pts, centers).tolist() == [0, 1, 0]


def test_nearest_argmin_chunks():
    rng = np.random.default_rng(3)
    pts = rng.random((100, 3))
    centers = rng.random((9, 3))
    assert nearest_argmin(pts, centers, chunk=16).tolist() == nearest_argmin(
        pts, centers, chunk=1000
    ).tolist()


def test_lab_dist2_shape_and_nonneg():
    a = np.random.default_rng(0).random((7, 3))
    b = np.random.default_rng(1).random((5, 3))
    d = lab_dist2(a, b)
    assert d.shape == (7, 5)
    assert np.all(d >= 0)


def test_redmean_dist2():
    a = np.array([[255, 0, 0]])
    b = np.array([[255, 0, 0], [0, 0, 0]])
    d = redmean_dist2(a, b)
    assert d[0, 0] == 0
    assert d[0, 1] > 0


def test_srgb_to_linear():
    assert srgb_to_linear(0.0) == 0.0
    assert srgb_to_linear(1.0) == pytest.approx(1.0)
    assert srgb_to_linear(0.04045) == pytest.approx(0.04045 / 12.92)
