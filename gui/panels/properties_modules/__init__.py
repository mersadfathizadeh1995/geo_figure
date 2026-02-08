"""Properties panel modules — mixin classes for each section."""
from geo_figure.gui.panels.properties_modules.collapsible_section import (
    CollapsibleSection,
)
from geo_figure.gui.panels.properties_modules.curve_info_section import (
    CurveInfoMixin,
)
from geo_figure.gui.panels.properties_modules.style_section import (
    StyleSectionMixin,
)
from geo_figure.gui.panels.properties_modules.processing_section import (
    ProcessingSectionMixin,
)
from geo_figure.gui.panels.properties_modules.ensemble_section import (
    EnsembleSectionMixin,
)

__all__ = [
    "CollapsibleSection",
    "CurveInfoMixin",
    "StyleSectionMixin",
    "ProcessingSectionMixin",
    "EnsembleSectionMixin",
]
