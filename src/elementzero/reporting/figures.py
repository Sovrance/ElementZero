"""Deterministic SVG figures for repository reports.

Figures are secondary to the machine-readable tables (WO-08 section 4), but they
still have to satisfy two repository rules: they are generated from committed
artifacts only, and they are byte-reproducible so that ``SHA256SUMS.txt`` keeps
verifying in a clean checkout. Both rules rule out a raster plotting backend, so
this module emits plain SVG with fixed-precision coordinates.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

WIDTH = 900
HEIGHT = 520
MARGIN_LEFT = 96
MARGIN_RIGHT = 220
MARGIN_TOP = 56
MARGIN_BOTTOM = 72

PALETTE: dict[str, str] = {
    "EZ-SEMF-LS-v1": "#1f77b4",
    "EZ-GP-DIRECT-v1": "#d62728",
    "EZ-SEMF-GP-RESIDUAL-v1": "#2ca02c",
}
FALLBACK_COLOURS = ("#7f7f7f", "#9467bd", "#8c564b", "#e377c2")

FONT = "font-family=\"DejaVu Sans, Helvetica, Arial, sans-serif\""


def colour_for(label: str, index: int = 0) -> str:
    return PALETTE.get(label, FALLBACK_COLOURS[index % len(FALLBACK_COLOURS)])


@dataclass(frozen=True)
class Series:
    """One labelled point cloud. Points are consumed in the given order."""

    label: str
    colour: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class BarGroup:
    """One x-axis group; ``values`` is aligned with the chart's series labels."""

    label: str
    values: tuple[float | None, ...]


def _fmt(value: float) -> str:
    """Fixed-precision coordinate text so byte output never depends on repr."""
    text = f"{value:.3f}"
    return "0.000" if text in {"-0.000", "nan", "inf", "-inf"} else text


def _tick_text(value: float) -> str:
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 10000 or magnitude < 0.01:
        return f"{value:.3g}"
    if magnitude >= 100:
        return f"{value:.0f}"
    if magnitude >= 1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _ticks(low: float, high: float, count: int = 5) -> list[float]:
    if high <= low:
        return [low]
    step = (high - low) / count
    return [low + step * i for i in range(count + 1)]


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _log10(value: float) -> float:
    """Log scale that keeps zero and negative inputs plottable at the floor."""
    return math.log10(value) if value > 0 else -3.0


class _Axes:
    def __init__(
        self,
        *,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        x_log: bool = False,
        y_log: bool = False,
    ) -> None:
        self.x_low, self.x_high = x_range
        self.y_low, self.y_high = y_range
        self.x_log = x_log
        self.y_log = y_log
        if self.x_high <= self.x_low:
            self.x_high = self.x_low + 1.0
        if self.y_high <= self.y_low:
            self.y_high = self.y_low + 1.0

    @property
    def plot_width(self) -> float:
        return WIDTH - MARGIN_LEFT - MARGIN_RIGHT

    @property
    def plot_height(self) -> float:
        return HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

    def px(self, x: float) -> float:
        value = _log10(x) if self.x_log else x
        low = _log10(self.x_low) if self.x_log else self.x_low
        high = _log10(self.x_high) if self.x_log else self.x_high
        return MARGIN_LEFT + (value - low) / (high - low) * self.plot_width

    def py(self, y: float) -> float:
        value = _log10(y) if self.y_log else y
        low = _log10(self.y_low) if self.y_log else self.y_low
        high = _log10(self.y_high) if self.y_log else self.y_high
        return HEIGHT - MARGIN_BOTTOM - (value - low) / (high - low) * self.plot_height


def _frame(
    *, title: str, x_label: str, y_label: str, axes: _Axes, x_tick_labels: Sequence[str] | None
) -> list[str]:
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{WIDTH // 2}" y="30" text-anchor="middle" {FONT} font-size="18" '
        f'fill="#111111">{_escape(title)}</text>',
        f'<rect x="{MARGIN_LEFT}" y="{MARGIN_TOP}" width="{_fmt(axes.plot_width)}" '
        f'height="{_fmt(axes.plot_height)}" fill="#fbfbfb" stroke="#333333" stroke-width="1"/>',
    ]
    for tick in _ticks(axes.y_low, axes.y_high):
        y = axes.py(10**tick if axes.y_log else tick)
        label = _tick_text(10**tick if axes.y_log else tick)
        out.append(
            f'<line x1="{MARGIN_LEFT}" y1="{_fmt(y)}" x2="{_fmt(MARGIN_LEFT + axes.plot_width)}" '
            f'y2="{_fmt(y)}" stroke="#e4e4e4" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{MARGIN_LEFT - 10}" y="{_fmt(y + 4)}" text-anchor="end" {FONT} '
            f'font-size="12" fill="#333333">{_escape(label)}</text>'
        )
    if x_tick_labels is None:
        for tick in _ticks(axes.x_low, axes.x_high):
            x = axes.px(10**tick if axes.x_log else tick)
            label = _tick_text(10**tick if axes.x_log else tick)
            out.append(
                f'<text x="{_fmt(x)}" y="{HEIGHT - MARGIN_BOTTOM + 20}" text-anchor="middle" '
                f'{FONT} font-size="12" fill="#333333">{_escape(label)}</text>'
            )
    else:
        count = len(x_tick_labels)
        for index, label in enumerate(x_tick_labels):
            x = MARGIN_LEFT + axes.plot_width * (index + 0.5) / count
            out.append(
                f'<text x="{_fmt(x)}" y="{HEIGHT - MARGIN_BOTTOM + 20}" text-anchor="middle" '
                f'{FONT} font-size="12" fill="#333333">{_escape(label)}</text>'
            )
    out.append(
        f'<text x="{MARGIN_LEFT + axes.plot_width / 2:.3f}" y="{HEIGHT - 22}" '
        f'text-anchor="middle" {FONT} font-size="13" fill="#111111">{_escape(x_label)}</text>'
    )
    out.append(
        f'<text x="26" y="{MARGIN_TOP + axes.plot_height / 2:.3f}" text-anchor="middle" {FONT} '
        f'font-size="13" fill="#111111" transform="rotate(-90 26 '
        f'{MARGIN_TOP + axes.plot_height / 2:.3f})">{_escape(y_label)}</text>'
    )
    return out


def _legend(labels: Sequence[str], colours: Sequence[str]) -> list[str]:
    out = []
    x = WIDTH - MARGIN_RIGHT + 18
    for index, (label, colour) in enumerate(zip(labels, colours)):
        y = MARGIN_TOP + 8 + index * 22
        out.append(
            f'<rect x="{x}" y="{y}" width="12" height="12" fill="{colour}" '
            f'stroke="#333333" stroke-width="0.5"/>'
        )
        out.append(
            f'<text x="{x + 18}" y="{y + 11}" {FONT} font-size="12" fill="#111111">'
            f"{_escape(label)}</text>"
        )
    return out


def scatter_svg(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series: Sequence[Series],
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
    x_log: bool = False,
    y_log: bool = False,
    identity_line: bool = False,
    radius: float = 2.4,
) -> str:
    points = [p for s in series for p in s.points]
    if not points:
        raise ValueError("a scatter figure needs at least one point")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    axes = _Axes(
        x_range=x_range or (min(xs), max(xs)),
        y_range=y_range or (min(ys), max(ys)),
        x_log=x_log,
        y_log=y_log,
    )
    out = _frame(title=title, x_label=x_label, y_label=y_label, axes=axes, x_tick_labels=None)
    if identity_line:
        low = max(axes.x_low, axes.y_low)
        high = min(axes.x_high, axes.y_high)
        out.append(
            f'<line x1="{_fmt(axes.px(low))}" y1="{_fmt(axes.py(low))}" '
            f'x2="{_fmt(axes.px(high))}" y2="{_fmt(axes.py(high))}" stroke="#555555" '
            f'stroke-width="1" stroke-dasharray="6 4"/>'
        )
    for item in series:
        for x, y in item.points:
            out.append(
                f'<circle cx="{_fmt(axes.px(x))}" cy="{_fmt(axes.py(y))}" r="{_fmt(radius)}" '
                f'fill="{item.colour}" fill-opacity="0.72"/>'
            )
    out.extend(_legend([s.label for s in series], [s.colour for s in series]))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def grouped_bar_svg(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series_labels: Sequence[str],
    colours: Sequence[str],
    groups: Sequence[BarGroup],
    y_range: tuple[float, float] | None = None,
    reference_lines: Sequence[tuple[float, str]] = (),
) -> str:
    values = [v for group in groups for v in group.values if v is not None]
    if not values:
        raise ValueError("a bar figure needs at least one value")
    high = max(values) if y_range is None else y_range[1]
    low = 0.0 if y_range is None else y_range[0]
    for level, _ in reference_lines:
        high = max(high, level)
    axes = _Axes(x_range=(0.0, float(len(groups))), y_range=(low, high * 1.08))
    out = _frame(
        title=title,
        x_label=x_label,
        y_label=y_label,
        axes=axes,
        x_tick_labels=[g.label for g in groups],
    )
    slot = axes.plot_width / len(groups)
    bar_width = slot * 0.72 / len(series_labels)
    for group_index, group in enumerate(groups):
        base = MARGIN_LEFT + slot * group_index + slot * 0.14
        for bar_index, value in enumerate(group.values):
            x = base + bar_width * bar_index
            if value is None:
                out.append(
                    f'<text x="{_fmt(x + bar_width / 2)}" y="{_fmt(axes.py(low) - 6)}" '
                    f'text-anchor="middle" {FONT} font-size="10" fill="#777777">n/a</text>'
                )
                continue
            top = axes.py(value)
            height = axes.py(low) - top
            out.append(
                f'<rect x="{_fmt(x)}" y="{_fmt(top)}" width="{_fmt(bar_width)}" '
                f'height="{_fmt(max(height, 0.0))}" fill="{colours[bar_index]}" '
                f'stroke="#333333" stroke-width="0.4"/>'
            )
    for level, label in reference_lines:
        y = axes.py(level)
        out.append(
            f'<line x1="{MARGIN_LEFT}" y1="{_fmt(y)}" x2="{_fmt(MARGIN_LEFT + axes.plot_width)}" '
            f'y2="{_fmt(y)}" stroke="#111111" stroke-width="1" stroke-dasharray="5 3"/>'
        )
        out.append(
            f'<text x="{_fmt(MARGIN_LEFT + axes.plot_width - 4)}" y="{_fmt(y - 5)}" '
            f'text-anchor="end" {FONT} font-size="11" fill="#111111">{_escape(label)}</text>'
        )
    out.extend(_legend(series_labels, colours))
    out.append("</svg>")
    return "\n".join(out) + "\n"
