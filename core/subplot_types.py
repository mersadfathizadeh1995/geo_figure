"""Subplot type registry and validation.

Defines the canonical subplot types and provides helpers
to check data compatibility and auto-assign types.
"""

# ── Type constants ────────────────────────────────────────────
UNSET = "unset"
DC = "dc"
VS_EXTRACT = "vs_extract"
PROFILE = "profile"
SOIL_PROFILE = "soil_profile"

ALL_TYPES = {UNSET, DC, VS_EXTRACT, PROFILE, SOIL_PROFILE}

# ── Data kind strings (used in validation) ────────────────────
KIND_CURVE = "curve"             # CurveData (experimental / theoretical DC)
KIND_ENSEMBLE = "ensemble"       # EnsembleData (theoretical DC set)
KIND_VS_PROFILE = "vs_profile"   # VsProfileData (extraction result)
KIND_SOIL_PROFILE = "soil_profile"  # SoilProfile / SoilProfileGroup

# ── Acceptance map ────────────────────────────────────────────
# For each subplot type, which data kinds can be placed on it.
_ACCEPTS = {
    UNSET:        {KIND_CURVE, KIND_ENSEMBLE, KIND_VS_PROFILE, KIND_SOIL_PROFILE},
    DC:           {KIND_CURVE, KIND_ENSEMBLE},
    VS_EXTRACT:   {KIND_VS_PROFILE, KIND_SOIL_PROFILE},
    PROFILE:      {KIND_VS_PROFILE, KIND_SOIL_PROFILE},
    SOIL_PROFILE: {KIND_SOIL_PROFILE},
}

# ── Auto-assignment: data kind -> subplot type ────────────────
_AUTO_TYPE = {
    KIND_CURVE:        DC,
    KIND_ENSEMBLE:     DC,
    KIND_VS_PROFILE:   VS_EXTRACT,
    KIND_SOIL_PROFILE: PROFILE,
}

# ── Display names (for error messages) ────────────────────────
_DISPLAY_NAMES = {
    UNSET:        "Blank",
    DC:           "Dispersion Curve",
    VS_EXTRACT:   "Vs Extraction",
    PROFILE:      "Profile",
    SOIL_PROFILE: "Soil Profile",
}

_KIND_DISPLAY = {
    KIND_CURVE:        "dispersion curve",
    KIND_ENSEMBLE:     "ensemble",
    KIND_VS_PROFILE:   "Vs extraction profile",
    KIND_SOIL_PROFILE: "soil profile",
}


def subplot_accepts(subplot_type: str, data_kind: str) -> bool:
    """Return True if *subplot_type* can hold data of *data_kind*."""
    accepted = _ACCEPTS.get(subplot_type, set())
    return data_kind in accepted


def auto_assign_type(current_type: str, data_kind: str) -> str:
    """Return the subplot type after adding *data_kind*.

    If *current_type* is UNSET, return the appropriate type for
    the data kind.  Otherwise return *current_type* unchanged.
    """
    if current_type == UNSET:
        return _AUTO_TYPE.get(data_kind, current_type)
    return current_type


def type_display_name(subplot_type: str) -> str:
    """Human-readable name for a subplot type."""
    return _DISPLAY_NAMES.get(subplot_type, subplot_type)


def kind_display_name(data_kind: str) -> str:
    """Human-readable name for a data kind."""
    return _KIND_DISPLAY.get(data_kind, data_kind)


def rejection_message(subplot_type: str, data_kind: str) -> str:
    """Build a user-facing error message for an incompatible add."""
    return (
        f"Cannot add {kind_display_name(data_kind)} to a "
        f"'{type_display_name(subplot_type)}' subplot.\n\n"
        f"Use an empty subplot or one of compatible type."
    )
