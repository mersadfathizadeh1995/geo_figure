"""Custom log-frequency axis for PyQtGraph plots."""
import numpy as np
import pyqtgraph as pg


class LogFreqAxis(pg.AxisItem):
    """X-axis that displays Hz values from log10-transformed coordinates.

    Generates ticks at "nice" values: 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100...
    """

    _NICE_MAJORS = [1, 2, 5]
    _NICE_MINORS = [1, 1.5, 2, 3, 4, 5, 6, 7, 8, 9]

    def tickValues(self, minVal, maxVal, size):
        """Generate tick positions at nice Hz values."""
        if minVal >= maxVal:
            return []

        if maxVal > 10 or minVal < -5:
            return super().tickValues(minVal, maxVal, size)

        hz_min = max(10 ** minVal, 0.01)
        try:
            hz_max = 10 ** maxVal
        except OverflowError:
            return super().tickValues(minVal, maxVal, size)

        ticks = []

        # Major ticks: 1-2-5 sequence across decades
        major_pos = []
        decade = 10 ** int(np.floor(np.log10(hz_min)))
        while decade <= hz_max * 10:
            for m in self._NICE_MAJORS:
                val = m * decade
                if hz_min <= val <= hz_max:
                    major_pos.append(np.log10(val))
            decade *= 10
        if major_pos:
            ticks.append((None, major_pos))

        # Minor ticks: fill in between
        minor_pos = []
        decade = 10 ** int(np.floor(np.log10(hz_min)))
        while decade <= hz_max * 10:
            for m in self._NICE_MINORS:
                val = m * decade
                lv = np.log10(val)
                if hz_min <= val <= hz_max and lv not in major_pos:
                    minor_pos.append(lv)
            decade *= 10
        if minor_pos:
            ticks.append((None, minor_pos))

        return ticks

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            try:
                hz = 10 ** v
                if hz >= 100:
                    strings.append(f"{hz:.0f}")
                elif hz >= 10:
                    strings.append(f"{hz:.0f}")
                elif hz >= 1:
                    strings.append(f"{hz:.1f}")
                else:
                    strings.append(f"{hz:.2f}")
            except (OverflowError, ValueError):
                strings.append("")
        return strings
