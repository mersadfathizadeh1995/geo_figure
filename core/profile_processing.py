"""Vs profile processing: resample, median, percentiles, sigma_ln, Vs30/Vs100.

Operates on paired-format profiles as output by Geopsy gpprofile:
  depths  = [0, d1, d1, d2, d2, d3]   (top1, bot1, top2, bot2, ...)
  velocities = [v1, v1, v2, v2, v3, v3]
  num_layers = len(depths) // 2
"""
import numpy as np
import warnings
from typing import List, Tuple, Dict, Optional


def resample_to_grid(
    depth_profile: np.ndarray,
    velocity_profile: np.ndarray,
    depth_grid: np.ndarray,
) -> np.ndarray:
    """Resample a single paired-format profile to a uniform depth grid.

    Step-function interpolation: each grid point gets the velocity of
    the layer it falls within. Beyond the last layer, extends halfspace.
    """
    n_rows = len(depth_profile)
    result = np.zeros_like(depth_grid)
    last_vel = velocity_profile[-1] if len(velocity_profile) > 0 else 0.0

    for i, z in enumerate(depth_grid):
        found = False
        for d in range(1, n_rows, 2):
            if d == 1:
                if z <= depth_profile[d]:
                    result[i] = velocity_profile[d]
                    found = True
                    break
            else:
                if depth_profile[d - 2] <= z < depth_profile[d]:
                    result[i] = velocity_profile[d]
                    found = True
                    break
        if not found:
            result[i] = last_vel
    return result


def calculate_median_paired(
    profiles: List[Tuple[np.ndarray, np.ndarray]],
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate row-wise median of profiles in paired format.

    All profiles must have the same number of rows.
    Returns (median_depth, median_velocity) in paired format.
    """
    n = len(profiles)
    n_rows = len(profiles[0][0])
    depth_arr = np.column_stack([p[0] for p in profiles])
    vel_arr = np.column_stack([p[1] for p in profiles])
    return np.median(depth_arr, axis=1), np.median(vel_arr, axis=1)


def calculate_statistics(
    profiles: List[Tuple[np.ndarray, np.ndarray]],
    dz: float = 0.1,
    z_max: float = 200.0,
    percentiles: Tuple[float, float] = (5, 95),
) -> Dict[str, np.ndarray]:
    """Compute depth-grid statistics from profiles in paired format.

    Returns dict with keys: depth_grid, median, p_low, p_high, sigma_ln, n_profiles.
    """
    depth_grid = np.arange(dz, z_max + dz, dz)
    n_depths = len(depth_grid)
    n_profiles = len(profiles)

    vel_array = np.zeros((n_depths, n_profiles))
    for i, (d, v) in enumerate(profiles):
        vel_array[:, i] = resample_to_grid(d, v, depth_grid)

    median = np.nanmedian(vel_array, axis=1)
    p_low = np.nanpercentile(vel_array, percentiles[0], axis=1)
    p_high = np.nanpercentile(vel_array, percentiles[1], axis=1)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pos = np.where(vel_array > 0, vel_array, np.nan)
        sigma_ln = np.nanstd(np.log(pos), axis=1, ddof=0)

    return {
        "depth_grid": depth_grid,
        "median": median,
        "p_low": p_low,
        "p_high": p_high,
        "sigma_ln": sigma_ln,
        "n_profiles": n_profiles,
    }


def calculate_vsN(
    profiles: List[Tuple[np.ndarray, np.ndarray]],
    target_depth_m: float = 30.0,
) -> np.ndarray:
    """Calculate time-averaged velocity over target_depth_m for each profile.

    VsN = target_depth / sum(thickness_i / Vs_i).
    Returns NaN for profiles not reaching target depth.
    """
    n = len(profiles)
    values = np.full(n, np.nan)

    for idx, (depth, vel) in enumerate(profiles):
        n_rows = len(depth)
        max_depth = np.max(depth[np.isfinite(depth)])
        if max_depth < target_depth_m:
            continue

        travel_time = 0.0
        for layer_start in range(0, n_rows - 1, 2):
            bot_idx = layer_start + 1
            if layer_start == 0:
                thickness = depth[bot_idx]
            else:
                thickness = depth[bot_idx] - depth[bot_idx - 2]
            layer_vel = vel[bot_idx]
            layer_bottom = depth[bot_idx]

            if layer_bottom <= target_depth_m and np.isfinite(layer_bottom):
                travel_time += thickness / layer_vel
            else:
                if layer_start == 0:
                    remaining = target_depth_m
                else:
                    remaining = target_depth_m - depth[bot_idx - 2]
                if remaining > 0:
                    travel_time += remaining / layer_vel
                break

        if travel_time > 0:
            values[idx] = target_depth_m / travel_time

    return values


def calculate_vs30(profiles):
    """Vs30 (30 m) in m/s."""
    return calculate_vsN(profiles, 30.0)


def calculate_vs100(profiles):
    """Vs100 (100 ft = 30.48 m) in ft/s."""
    vals = calculate_vsN(profiles, 30.48)
    return vals * 3.28084  # m/s -> ft/s


def process_profiles(
    profiles: List[Tuple[np.ndarray, np.ndarray]],
    dz: float = 0.1,
    z_max: float = 200.0,
    percentiles: Tuple[float, float] = (5, 95),
) -> Dict:
    """Full processing pipeline: statistics + VsN + median paired.

    Returns dict suitable for creating VsProfileData.
    """
    stats = calculate_statistics(profiles, dz, z_max, percentiles)

    # Layered median
    try:
        med_depth, med_vel = calculate_median_paired(profiles)
    except Exception:
        med_depth, med_vel = None, None

    vs30 = calculate_vs30(profiles)
    vs100 = calculate_vs100(profiles)

    return {
        **stats,
        "median_depth_paired": med_depth,
        "median_vel_paired": med_vel,
        "vs30_values": vs30,
        "vs100_values": vs100,
    }
