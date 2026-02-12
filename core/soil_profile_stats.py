"""Statistics computation for SoilProfileGroup.

Computes median, percentile bands across a group of SoilProfile models
by interpolating them onto a common depth grid.
"""

import numpy as np

from geo_figure.core.models import SoilProfileGroup


def compute_group_statistics(
    group: SoilProfileGroup,
    depth_step: float = 0.5,
    render_property: str = "vs",
):
    """Compute median and percentile statistics for a profile group.

    Interpolates all profiles onto a uniform depth grid (step-function
    interpolation preserving layer boundaries), then computes per-depth
    median and 5th/95th percentiles.  The grid extends past the deepest
    finite interface by a halfspace margin so that statistics visually
    cover the same range as the individual profiles.

    Parameters
    ----------
    group : SoilProfileGroup
        Group with at least 2 visible profiles.
    depth_step : float
        Grid spacing in metres (default 0.5 m).
    render_property : str
        Property to compute stats for: "vs", "vp", or "density".

    Returns
    -------
    bool
        True if statistics were computed successfully.
    """
    visible = [p for p in group.profiles if p.visible]
    if len(visible) < 2:
        return False

    # Determine max finite depth and halfspace extension across all profiles
    max_depth = 0.0
    max_hs_extension = 0.15  # default fraction
    for p in visible:
        vals = _get_property(p, render_property)
        if vals is None:
            continue
        finite_bots = p.bot_depth[np.isfinite(p.bot_depth)]
        if len(finite_bots) > 0:
            md = float(finite_bots.max())
            max_depth = max(max_depth, md)
        elif len(p.top_depth) > 0:
            max_depth = max(max_depth, float(p.top_depth[-1]) + 50.0)
        hs = getattr(p, "halfspace_extension", 0.15)
        if hs > max_hs_extension:
            max_hs_extension = hs

    if max_depth <= 0:
        return False

    # Extend grid into halfspace region (same visual range as profiles)
    hs_depth = max_depth * max_hs_extension
    grid_max = max_depth + hs_depth

    # Create uniform depth grid
    depth_grid = np.arange(0.0, grid_max + depth_step, depth_step)

    # Interpolate each profile onto the grid (step-function)
    matrix = []
    for p in visible:
        vals = _get_property(p, render_property)
        if vals is None:
            continue
        interp = _step_interpolate(p.top_depth, p.bot_depth, vals, depth_grid)
        if interp is not None:
            matrix.append(interp)

    if len(matrix) < 2:
        return False

    matrix = np.array(matrix)  # shape: (n_profiles, n_depths)

    # Compute statistics per depth
    group.depth_grid = depth_grid
    group.median_values = np.nanmedian(matrix, axis=0)
    group.p05_values = np.nanpercentile(matrix, 5, axis=0)
    group.p95_values = np.nanpercentile(matrix, 95, axis=0)
    group.stats_property = render_property

    return True


def _get_property(profile, prop: str):
    """Get the array for the requested property."""
    if prop == "vs":
        return profile.vs
    elif prop == "vp":
        return profile.vp
    elif prop == "density":
        return profile.density
    return profile.vs


def _step_interpolate(top_depth, bot_depth, values, depth_grid):
    """Interpolate a step-function profile onto a uniform depth grid.

    For each grid point, finds which layer it falls in and assigns that
    layer's value. Points below the deepest finite interface get the
    halfspace (last layer) value.
    """
    n_layers = len(values)
    if n_layers == 0:
        return None

    result = np.full(len(depth_grid), np.nan)

    for i, d in enumerate(depth_grid):
        assigned = False
        for j in range(n_layers):
            td = top_depth[j]
            bd = bot_depth[j]
            if not np.isfinite(bd):
                # Halfspace: everything from top_depth downward
                if d >= td:
                    result[i] = values[j]
                    assigned = True
                    break
            else:
                if td <= d < bd:
                    result[i] = values[j]
                    assigned = True
                    break
        if not assigned and n_layers > 0:
            # Below all layers — use halfspace value
            result[i] = values[-1]

    return result
