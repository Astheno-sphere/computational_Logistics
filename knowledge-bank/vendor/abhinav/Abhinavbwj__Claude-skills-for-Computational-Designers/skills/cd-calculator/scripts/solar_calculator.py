#!/usr/bin/env python3
"""
Solar Calculator for AEC Computational Design
================================================
Computes solar position, shadow geometry, PV parameters, and annual radiation
for any location on Earth at any date and time.

Based on Spencer (1971) and ASHRAE solar geometry equations.

Usage:
    python solar_calculator.py --latitude 51.5 --longitude -0.12 --date 2025-06-21 --time 12:00
    python solar_calculator.py --latitude 25.2 --longitude 55.3 --annual-summary
    python solar_calculator.py --latitude 40.7 --longitude -74.0 --shadow-analysis --object-height 30
    python solar_calculator.py --latitude 52.5 --longitude 13.4 --pv-tilt
"""

import argparse
import json
import math
import sys
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Solar geometry functions
# ---------------------------------------------------------------------------

def day_of_year(date_str):
    """Return day of year (1-365/366) from 'YYYY-MM-DD'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.timetuple().tm_yday


def solar_declination(n):
    """Solar declination angle in degrees. n = day of year."""
    B = math.radians((360 / 365) * (n - 81))
    delta = 23.45 * math.sin(B)
    return delta


def equation_of_time(n):
    """Equation of time correction in minutes. n = day of year."""
    B = math.radians((360 / 365) * (n - 81))
    EoT = (9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B))
    return EoT


def hour_angle(solar_time_hours):
    """Hour angle in degrees. solar_time_hours: 0-24, noon = 12."""
    return 15.0 * (solar_time_hours - 12.0)


def solar_altitude(lat, delta, omega):
    """Solar altitude angle in degrees."""
    lat_r = math.radians(lat)
    delta_r = math.radians(delta)
    omega_r = math.radians(omega)

    sin_alpha = (math.sin(lat_r) * math.sin(delta_r) +
                 math.cos(lat_r) * math.cos(delta_r) * math.cos(omega_r))
    sin_alpha = max(-1.0, min(1.0, sin_alpha))
    return math.degrees(math.asin(sin_alpha))


def solar_azimuth(lat, delta, omega, alpha):
    """Solar azimuth angle in degrees (0=North, 90=East, 180=South, 270=West)."""
    lat_r = math.radians(lat)
    delta_r = math.radians(delta)
    omega_r = math.radians(omega)
    alpha_r = math.radians(alpha)

    cos_alpha = math.cos(alpha_r)
    if abs(cos_alpha) < 1e-10:
        return 180.0  # sun at zenith

    # Use atan2 for correct quadrant
    sin_az = -math.sin(omega_r) * math.cos(delta_r) / cos_alpha
    cos_az = ((math.sin(alpha_r) * math.sin(lat_r) - math.sin(delta_r)) /
              (cos_alpha * math.cos(lat_r)))
    cos_az = max(-1.0, min(1.0, cos_az))

    az = math.degrees(math.atan2(sin_az, cos_az))
    # Convert from math convention to compass (0=North, clockwise)
    az = (az + 360) % 360
    # Adjust: atan2 gives 0=South convention; flip to 0=North
    az = (180 + az) % 360

    return az


def sunrise_sunset(lat, delta):
    """
    Compute sunrise and sunset solar times, and day length.
    Returns (sunrise_hours, sunset_hours, day_length_hours) or None if polar day/night.
    """
    lat_r = math.radians(lat)
    delta_r = math.radians(delta)

    cos_omega_s = -math.tan(lat_r) * math.tan(delta_r)

    if cos_omega_s < -1:
        # Polar day (midnight sun)
        return 0.0, 24.0, 24.0
    elif cos_omega_s > 1:
        # Polar night
        return None, None, 0.0

    omega_s = math.degrees(math.acos(cos_omega_s))
    sunrise = 12.0 - omega_s / 15.0
    sunset = 12.0 + omega_s / 15.0
    day_length = 2 * omega_s / 15.0

    return sunrise, sunset, day_length


def shadow_length(object_height, altitude_deg):
    """Shadow length for a given object height and solar altitude."""
    if altitude_deg <= 0:
        return float('inf')  # sun below horizon
    return object_height / math.tan(math.radians(altitude_deg))


def optimal_pv_tilt(lat):
    """Simple rule: optimal annual fixed tilt ~ latitude."""
    return abs(lat)


def extraterrestrial_radiation(n, lat):
    """Daily extraterrestrial radiation on horizontal surface (MJ/m^2/day)."""
    I_sc = 1367  # W/m^2, solar constant
    lat_r = math.radians(lat)
    delta = solar_declination(n)
    delta_r = math.radians(delta)

    # Eccentricity correction
    E0 = 1 + 0.033 * math.cos(math.radians(360 * n / 365))

    cos_omega_s = -math.tan(lat_r) * math.tan(delta_r)
    cos_omega_s = max(-1.0, min(1.0, cos_omega_s))

    if cos_omega_s <= -1:
        omega_s = math.pi  # 180 degrees
    elif cos_omega_s >= 1:
        omega_s = 0  # polar night
    else:
        omega_s = math.acos(cos_omega_s)

    H0 = (24 * 3600 / math.pi) * I_sc * E0 * (
        math.cos(lat_r) * math.cos(delta_r) * math.sin(omega_s) +
        omega_s * math.sin(lat_r) * math.sin(delta_r)
    )
    # Convert from J/m^2 to MJ/m^2
    return H0 / 1e6


def format_time(hours):
    """Convert decimal hours to HH:MM string."""
    if hours is None:
        return "--:--"
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h:02d}:{m:02d}"


def format_day_length(hours):
    """Format day length as Xh Ym."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m:02d}m"


def azimuth_direction(az):
    """Return compass direction string for an azimuth angle."""
    dirs = [
        (0, "N"), (22.5, "NNE"), (45, "NE"), (67.5, "ENE"),
        (90, "E"), (112.5, "ESE"), (135, "SE"), (157.5, "SSE"),
        (180, "S"), (202.5, "SSW"), (225, "SW"), (247.5, "WSW"),
        (270, "W"), (292.5, "WNW"), (315, "NW"), (337.5, "NNW"),
        (360, "N"),
    ]
    for i in range(len(dirs) - 1):
        if az < (dirs[i][0] + dirs[i + 1][0]) / 2:
            return dirs[i][1]
    return "N"


# ---------------------------------------------------------------------------
# Mode functions
# ---------------------------------------------------------------------------

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
# Representative day of each month (Klein, 1977)
MONTH_REP_DAYS = [17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344]


def compute_position(lat, lon, date_str, time_str):
    """Compute solar position for a specific date and time."""
    n = day_of_year(date_str)
    delta = solar_declination(n)

    time_parts = time_str.split(":")
    solar_hour = float(time_parts[0]) + float(time_parts[1]) / 60.0

    omega = hour_angle(solar_hour)
    alt = solar_altitude(lat, delta, omega)
    az = solar_azimuth(lat, delta, omega, alt)
    sr, ss, dl = sunrise_sunset(lat, delta)

    shadow_per_m = shadow_length(1.0, alt) if alt > 0 else float('inf')
    shadow_dir = (az + 180) % 360 if alt > 0 else None

    result = {
        "mode": "position",
        "latitude": lat,
        "longitude": lon,
        "date": date_str,
        "solar_time": time_str,
        "day_of_year": n,
        "declination_deg": round(delta, 4),
        "hour_angle_deg": round(omega, 4),
        "altitude_deg": round(alt, 4),
        "azimuth_deg": round(az, 4),
        "azimuth_direction": azimuth_direction(az),
        "sunrise_solar_time": format_time(sr),
        "sunset_solar_time": format_time(ss),
        "day_length": format_day_length(dl),
        "day_length_hours": round(dl, 2),
        "shadow_length_per_m": round(shadow_per_m, 4) if shadow_per_m != float('inf') else "infinite (sun below horizon)",
        "shadow_direction_deg": round(shadow_dir, 2) if shadow_dir is not None else None,
    }
    return result


def compute_annual_summary(lat, lon):
    """Monthly solar data summary."""
    months = []
    total_annual_radiation = 0

    for m in range(12):
        n = MONTH_REP_DAYS[m]
        delta = solar_declination(n)
        sr, ss, dl = sunrise_sunset(lat, delta)

        # Noon altitude
        omega_noon = 0
        alt_noon = solar_altitude(lat, delta, omega_noon)

        # Daily extraterrestrial radiation
        H0 = extraterrestrial_radiation(n, lat)

        # Estimate clearness index based on latitude band
        abs_lat = abs(lat)
        if abs_lat < 25:
            kt = 0.60
        elif abs_lat < 40:
            kt = 0.52
        elif abs_lat < 55:
            kt = 0.45
        else:
            kt = 0.38

        daily_radiation = H0 * kt  # MJ/m^2/day
        monthly_radiation = daily_radiation * MONTH_DAYS[m]
        total_annual_radiation += monthly_radiation

        months.append({
            "month": MONTH_NAMES[m],
            "representative_day": n,
            "declination_deg": round(delta, 2),
            "noon_altitude_deg": round(alt_noon, 2),
            "sunrise": format_time(sr),
            "sunset": format_time(ss),
            "day_length_hours": round(dl, 2),
            "daily_radiation_MJ_m2": round(daily_radiation, 2),
            "monthly_radiation_MJ_m2": round(monthly_radiation, 1),
        })

    result = {
        "mode": "annual_summary",
        "latitude": lat,
        "longitude": lon,
        "clearness_index": round(kt, 2),
        "annual_radiation_MJ_m2": round(total_annual_radiation, 1),
        "annual_radiation_kWh_m2": round(total_annual_radiation / 3.6, 1),
        "optimal_pv_tilt_deg": round(optimal_pv_tilt(lat), 1),
        "months": months,
    }
    return result


def compute_shadow_analysis(lat, lon, object_height):
    """Shadow length analysis at solstices and equinoxes at multiple times."""
    key_days = [
        ("Spring Equinox", 80),
        ("Summer Solstice", 172),
        ("Autumn Equinox", 266),
        ("Winter Solstice", 355),
    ]
    hours = [8, 10, 12, 14, 16]

    analyses = []
    for day_name, n in key_days:
        delta = solar_declination(n)
        sr, ss, dl = sunrise_sunset(lat, delta)

        day_data = {
            "day": day_name,
            "day_of_year": n,
            "declination_deg": round(delta, 2),
            "sunrise": format_time(sr),
            "sunset": format_time(ss),
            "day_length": format_day_length(dl),
            "shadows": [],
        }

        for h in hours:
            omega = hour_angle(h)
            alt = solar_altitude(lat, delta, omega)
            az = solar_azimuth(lat, delta, omega, alt)

            if alt > 0:
                s_len = shadow_length(object_height, alt)
                s_dir = (az + 180) % 360
            else:
                s_len = None
                s_dir = None

            day_data["shadows"].append({
                "solar_time": f"{h:02d}:00",
                "altitude_deg": round(alt, 2),
                "azimuth_deg": round(az, 2),
                "shadow_length_m": round(s_len, 2) if s_len is not None else "below horizon",
                "shadow_direction_deg": round(s_dir, 2) if s_dir is not None else None,
            })

        analyses.append(day_data)

    result = {
        "mode": "shadow_analysis",
        "latitude": lat,
        "longitude": lon,
        "object_height_m": object_height,
        "analyses": analyses,
    }
    return result


def compute_pv_tilt(lat, lon):
    """PV tilt optimization."""
    annual_tilt = optimal_pv_tilt(lat)

    monthly_tilts = []
    annual_energy_fixed = 0
    annual_energy_seasonal = 0

    for m in range(12):
        n = MONTH_REP_DAYS[m]
        delta = solar_declination(n)
        monthly_tilt = abs(lat) - delta if lat >= 0 else abs(lat) + delta
        monthly_tilt = max(0, min(90, monthly_tilt))

        H0 = extraterrestrial_radiation(n, lat)
        abs_lat = abs(lat)
        if abs_lat < 25:
            kt = 0.60
        elif abs_lat < 40:
            kt = 0.52
        elif abs_lat < 55:
            kt = 0.45
        else:
            kt = 0.38

        daily_h = H0 * kt
        # Tilted surface gain factor (approximate)
        fixed_factor = 1 + 0.3 * math.cos(math.radians(abs(annual_tilt - abs(lat)) + 5))
        seasonal_factor = 1 + 0.3 * math.cos(math.radians(abs(monthly_tilt - abs(lat)) + 2))

        daily_fixed = daily_h * fixed_factor
        daily_seasonal = daily_h * seasonal_factor

        annual_energy_fixed += daily_fixed * MONTH_DAYS[m]
        annual_energy_seasonal += daily_seasonal * MONTH_DAYS[m]

        monthly_tilts.append({
            "month": MONTH_NAMES[m],
            "optimal_tilt_deg": round(monthly_tilt, 1),
            "daily_radiation_fixed_MJ_m2": round(daily_fixed, 2),
            "daily_radiation_seasonal_MJ_m2": round(daily_seasonal, 2),
        })

    result = {
        "mode": "pv_tilt",
        "latitude": lat,
        "longitude": lon,
        "optimal_annual_tilt_deg": round(annual_tilt, 1),
        "annual_radiation_fixed_tilt_kWh_m2": round(annual_energy_fixed / 3.6, 1),
        "annual_radiation_seasonal_tilt_kWh_m2": round(annual_energy_seasonal / 3.6, 1),
        "seasonal_gain_percent": round((annual_energy_seasonal / annual_energy_fixed - 1) * 100, 1),
        "monthly_tilts": monthly_tilts,
    }
    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_position(r):
    print("=" * 48)
    print("  SOLAR CALCULATOR - Position")
    print("=" * 48)
    print()
    ns = "N" if r["latitude"] >= 0 else "S"
    ew = "E" if r["longitude"] >= 0 else "W"
    print(f"  Location:")
    print(f"    Latitude         : {abs(r['latitude']):.3f} deg {ns}")
    print(f"    Longitude        : {abs(r['longitude']):.3f} deg {ew}")
    print(f"    Date             : {r['date']}")
    print()
    print(f"  Solar Position at {r['solar_time']}:")
    print(f"    Altitude         : {r['altitude_deg']:.2f} deg")
    print(f"    Azimuth          : {r['azimuth_deg']:.2f} deg ({r['azimuth_direction']})")
    print()
    print(f"  Day Information:")
    print(f"    Sunrise          : {r['sunrise_solar_time']} solar time")
    print(f"    Sunset           : {r['sunset_solar_time']} solar time")
    print(f"    Day Length       : {r['day_length']}")
    print()
    print(f"  Shadow (per 1m object):")
    sl = r['shadow_length_per_m']
    if isinstance(sl, str):
        print(f"    Shadow Length    : {sl}")
    else:
        print(f"    Shadow Length    : {sl:.2f} m")
    sd = r['shadow_direction_deg']
    if sd is not None:
        print(f"    Shadow Direction : {sd:.2f} deg ({azimuth_direction(sd)})")
    print("=" * 48)


def print_annual_summary(r):
    print("=" * 64)
    print("  SOLAR CALCULATOR - Annual Summary")
    print("=" * 64)
    print()
    ns = "N" if r["latitude"] >= 0 else "S"
    ew = "E" if r["longitude"] >= 0 else "W"
    print(f"  Location: {abs(r['latitude']):.2f} deg {ns}, {abs(r['longitude']):.2f} deg {ew}")
    print(f"  Clearness Index: {r['clearness_index']}")
    print()
    print(f"  {'Month':<12} {'Noon Alt':>9} {'Sunrise':>8} {'Sunset':>8} {'Day Len':>8} {'Daily MJ':>9} {'Monthly MJ':>11}")
    print(f"  {'-'*12} {'-'*9} {'-'*8} {'-'*8} {'-'*8} {'-'*9} {'-'*11}")
    for m in r["months"]:
        print(f"  {m['month']:<12} {m['noon_altitude_deg']:>8.1f}° {m['sunrise']:>8} {m['sunset']:>8} "
              f"{m['day_length_hours']:>7.1f}h {m['daily_radiation_MJ_m2']:>8.1f} {m['monthly_radiation_MJ_m2']:>10.0f}")
    print()
    print(f"  Annual Radiation   : {r['annual_radiation_MJ_m2']:,.0f} MJ/m^2")
    print(f"                     : {r['annual_radiation_kWh_m2']:,.0f} kWh/m^2")
    print(f"  Optimal PV Tilt    : {r['optimal_pv_tilt_deg']:.1f} deg")
    print("=" * 64)


def print_shadow_analysis(r):
    print("=" * 64)
    print("  SOLAR CALCULATOR - Shadow Analysis")
    print("=" * 64)
    print()
    print(f"  Object Height: {r['object_height_m']:.1f} m")
    print()
    for day in r["analyses"]:
        print(f"  --- {day['day']} (day {day['day_of_year']}) ---")
        print(f"  Sunrise: {day['sunrise']}  |  Sunset: {day['sunset']}  |  Day: {day['day_length']}")
        print(f"  {'Time':>6} {'Altitude':>9} {'Azimuth':>9} {'Shadow':>10} {'Direction':>10}")
        for s in day["shadows"]:
            alt_str = f"{s['altitude_deg']:.1f} deg"
            az_str = f"{s['azimuth_deg']:.1f} deg"
            if isinstance(s['shadow_length_m'], str):
                sh_str = s['shadow_length_m']
                dir_str = "--"
            else:
                sh_str = f"{s['shadow_length_m']:.1f} m"
                dir_str = f"{s['shadow_direction_deg']:.0f} deg"
            print(f"  {s['solar_time']:>6} {alt_str:>9} {az_str:>9} {sh_str:>10} {dir_str:>10}")
        print()
    print("=" * 64)


def print_pv_tilt(r):
    print("=" * 60)
    print("  SOLAR CALCULATOR - PV Tilt Optimization")
    print("=" * 60)
    print()
    ns = "N" if r["latitude"] >= 0 else "S"
    print(f"  Latitude           : {abs(r['latitude']):.2f} deg {ns}")
    print(f"  Optimal Annual Tilt: {r['optimal_annual_tilt_deg']:.1f} deg")
    print()
    print(f"  Annual Radiation (fixed tilt)   : {r['annual_radiation_fixed_tilt_kWh_m2']:,.0f} kWh/m^2")
    print(f"  Annual Radiation (seasonal adj.): {r['annual_radiation_seasonal_tilt_kWh_m2']:,.0f} kWh/m^2")
    print(f"  Seasonal Adjustment Gain        : +{r['seasonal_gain_percent']:.1f}%")
    print()
    print(f"  {'Month':<12} {'Tilt':>8} {'Fixed MJ/d':>11} {'Seasonal MJ/d':>14}")
    print(f"  {'-'*12} {'-'*8} {'-'*11} {'-'*14}")
    for m in r["monthly_tilts"]:
        print(f"  {m['month']:<12} {m['optimal_tilt_deg']:>7.1f}° {m['daily_radiation_fixed_MJ_m2']:>10.2f} {m['daily_radiation_seasonal_MJ_m2']:>13.2f}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Solar Calculator - Position, shadows, radiation, and PV tilt"
    )
    parser.add_argument("--latitude", type=float, required=True, help="Site latitude (-90 to 90)")
    parser.add_argument("--longitude", type=float, required=True, help="Site longitude (-180 to 180)")
    parser.add_argument("--date", type=str, default=None, help="Date YYYY-MM-DD")
    parser.add_argument("--time", type=str, default="12:00", help="Solar time HH:MM (default 12:00)")
    parser.add_argument("--annual-summary", action="store_true", help="Monthly solar data summary")
    parser.add_argument("--shadow-analysis", action="store_true", help="Shadow length analysis")
    parser.add_argument("--object-height", type=float, default=10.0, help="Object height in meters (for shadow analysis)")
    parser.add_argument("--pv-tilt", action="store_true", help="Optimal PV tilt calculation")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Validate latitude / longitude
    if args.latitude < -90 or args.latitude > 90:
        print("ERROR: Latitude must be between -90 and 90.", file=sys.stderr)
        sys.exit(1)
    if args.longitude < -180 or args.longitude > 180:
        print("ERROR: Longitude must be between -180 and 180.", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    if args.annual_summary:
        result = compute_annual_summary(args.latitude, args.longitude)
        printer = print_annual_summary
    elif args.shadow_analysis:
        if args.object_height <= 0:
            print("ERROR: --object-height must be positive.", file=sys.stderr)
            sys.exit(1)
        result = compute_shadow_analysis(args.latitude, args.longitude, args.object_height)
        printer = print_shadow_analysis
    elif args.pv_tilt:
        result = compute_pv_tilt(args.latitude, args.longitude)
        printer = print_pv_tilt
    else:
        # Position mode requires a date
        if args.date is None:
            # Default to today
            args.date = datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("ERROR: Date must be in YYYY-MM-DD format.", file=sys.stderr)
            sys.exit(1)
        result = compute_position(args.latitude, args.longitude, args.date, args.time)
        printer = print_position

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        printer(result)


if __name__ == "__main__":
    main()
