"""
Real-Time Safety Index (RT-SI) Service

Implements the RT-SI methodology:
1. Historical severity-weighted crash rate
2. Empirical Bayes stabilization
3. Real-time uplift factors (speed, variance, conflicts)
4. VRU and Vehicle sub-indices
5. Combined and scaled index (0-100)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import numpy as np

from .db_client import VTTIPostgresClient
from ..core.intersection_mapping import (
    normalize_intersection_name,
    reverse_lookup_intersection,
)

logger = logging.getLogger(__name__)
# Respect the application's logging configuration: ensure INFO level and allow propagation
logger.setLevel(logging.INFO)
logger.propagate = True
# Ensure root logger has a handler and is at INFO level (fallback for environments
# where the application's logging config hasn't run yet). This is temporary and
# intended for debugging only.
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(level=logging.INFO)
root_logger.setLevel(logging.INFO)


class RTSIService:
    """Calculate Real-Time Safety Index for intersections."""

    # Optimal lambda from cross-validation (run find_lambda.py first)
    # Updated to 100000 based on cross-validation results
    LAMBDA = 100000.0
    R0 = 3.365  # Pooled mean rate from cross-validation

    # Severity weights
    W_FATAL = 10.0
    W_INJURY = 3.0
    W_PDO = 1.0

    # Scaling constants for uplift factors
    K1_SPEED = 1.5  # Speed reduction factor
    K2_VAR = 1.0  # Speed variance factor
    K3_CONF = 0.5  # Conflict factor
    K4_VRU_RATIO = 1.0  # VRU ratio factor
    K5_VOL_CAPACITY = 1.0  # Volume/capacity factor

    # Beta coefficients for uplift combination
    BETA1 = 0.3  # Speed uplift weight
    BETA2 = 0.3  # Variance uplift weight
    BETA3 = 0.4  # Conflict uplift weight

    # Gamma: base multiplier for indices
    GAMMA = 1.0

    # Omega: VRU vs Vehicle blend
    OMEGA_VRU = 0.6  # VRU weight (policy-driven, higher in urban areas)
    OMEGA_VEH = 0.4  # Vehicle weight

    # Assumed capacity (vehicles per 15-min bin)
    DEFAULT_CAPACITY = 500.0

    def __init__(self, db_client: VTTIPostgresClient):
        self.db_client = db_client

    def _to_short_name(self, intersection) -> str:
        """
        Ensure we use the normalized short name for real-time tables.

        If `intersection` is a string, normalize it. If it's an int (crash id),
        return it unchanged as caller should provide a realtime_intersection
        string when needed.
        """
        try:
            if isinstance(intersection, str):
                return normalize_intersection_name(intersection)
        except Exception:
            pass
        return intersection

    def get_historical_crash_rate(
        self, intersection_id: int, start_year: int = 2017, end_year: int = 2024
    ) -> Dict:
        """
        Get historical severity-weighted crash rate for intersection-time bin.

        Returns dict with:
        - weighted_crashes: severity-weighted crash count
        - exposure: total vehicle volume
        - raw_rate: crashes per vehicle
        """
        # Query crashes for the intersection across the provided year range.
        params = {
            "intersection_id": intersection_id,
            "w_fatal": self.W_FATAL,
            "w_injury": self.W_INJURY,
            "w_pdo": self.W_PDO,
            "start_year": start_year,
            "end_year": end_year,
        }

        query = f"""
        SELECT
            COALESCE(
                COUNT(*) FILTER (WHERE crash_severity IN ('K', 'Fatal')) * %(w_fatal)s +
                COUNT(*) FILTER (WHERE crash_severity IN ('A', 'B', 'Injury')) * %(w_injury)s +
                COUNT(*) * %(w_pdo)s,
                0
            ) as weighted_crashes,
            1 as exposure
        FROM vdot_crashes_with_intersections
        WHERE matched_intersection_id = %(intersection_id)s
          AND crash_year BETWEEN %(start_year)s AND %(end_year)s;
        """

        results = self.db_client.execute_query(query, params)

        if not results:
            return {"weighted_crashes": 0, "exposure": 1, "raw_rate": 0.0}

        row = results[0]
        crashes = float(row["weighted_crashes"]) if row["weighted_crashes"] else 0.0
        exposure = max(
            float(row["exposure"]) if row["exposure"] else 1.0, 1.0
        )  # Avoid division by zero
        raw_rate = crashes / exposure

        return {
            "weighted_crashes": crashes,
            "exposure": exposure,
            "raw_rate": raw_rate,
        }

    def compute_eb_rate(self, raw_rate: float, exposure: float) -> float:
        """
        Compute Empirical Bayes stabilized rate.

        r_hat = α * r + (1 - α) * r0
        where α = E / (E + λ)
        """
        alpha = exposure / (exposure + self.LAMBDA)
        r_hat = alpha * raw_rate + (1 - alpha) * self.R0
        return r_hat

    def get_intersection_capacity(
        self, intersection_id, bin_minutes: int = 15, lookback_days: int = 30
    ) -> float:
        """
        Compute intersection capacity as the 95th percentile of historical vehicle counts.

        Args:
            intersection_id: BSM intersection name (e.g., 'glebe-potomac')
            bin_minutes: Time bin size in minutes
            lookback_days: How many days of historical data to use

        Returns:
            Capacity value (95th percentile of vehicle counts), or DEFAULT_CAPACITY if insufficient data
        """
        try:
            # Get historical vehicle counts for the last N days
            lookback_us = (
                lookback_days * 24 * 60 * 60 * 1000000
            )  # Convert days to microseconds

            capacity_query = """
            SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY count) as capacity
            FROM "vehicle-count"
            WHERE intersection = %(intersection_id)s::text
              AND publish_timestamp >= (EXTRACT(EPOCH FROM NOW()) * 1000000 - %(lookback_us)s)::bigint;
            """

            # Try using the provided intersection_id first (may be full name)
            intersection_identifier = self._to_short_name(intersection_id)
            result = self.db_client.execute_query(
                capacity_query,
                {
                    "intersection_id": intersection_identifier,
                    "lookback_us": lookback_us,
                },
            )

            # If no result and intersection_id is a short name, try reverse lookup
            # No reverse-lookup fallback: we rely on normalized short names
            # being used for real-time tables. If no capacity found, we'll
            # fall back to DEFAULT_CAPACITY below.

            if result and result[0]["capacity"]:
                capacity = float(result[0]["capacity"])
                logger.info(
                    f"Computed capacity for {intersection_id}: {capacity:.0f} vehicles/{bin_minutes}min "
                    f"(95th percentile over {lookback_days} days)"
                )
                return capacity
            else:
                logger.warning(
                    f"No historical data for capacity calculation for {intersection_id}, "
                    f"using default: {self.DEFAULT_CAPACITY}"
                )
                return self.DEFAULT_CAPACITY

        except Exception as e:
            logger.warning(
                f"Error computing capacity for {intersection_id}: {e}, "
                f"using default: {self.DEFAULT_CAPACITY}"
            )
            return self.DEFAULT_CAPACITY

    def get_data_at_specific_time(
        self,
        intersection_id,
        timestamp: datetime,
        bin_minutes: int = 15,
    ) -> Optional[Dict]:
        """
        Get traffic data for a specific time bin only - no lookback.
        Used for trend analysis where we want data only from the exact time bin.

        Args:
            intersection_id: Can be int (crash intersection ID) or str (BSM intersection name)
            timestamp: Time to query data for
            bin_minutes: Time bin size in minutes

        Returns dict with traffic data, or None if no data exists for this time bin.
        """
        end_time = timestamp + timedelta(minutes=bin_minutes)
        start_time_us = int(timestamp.timestamp() * 1000000)
        end_time_us = int(end_time.timestamp() * 1000000)

        # Normalize to short-name for real-time tables
        intersection_identifier = self._to_short_name(intersection_id)

        # Query vehicle count and turning movements
        vehicle_query = """
        SELECT 
            SUM(count) as vehicle_count,
            SUM(CASE WHEN movement IN ('LT', 'RT', 'UT') THEN count ELSE 0 END) as turning_count
        FROM "vehicle-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s;
        """

        # Query speed distribution grouped by bin; compute metrics in Python for robustness
        speed_query = """
        SELECT
            speed_interval,
            SUM(count) as bin_count
        FROM "speed-distribution"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s
        GROUP BY speed_interval;
        """

        # Query VRU count
        vru_query = """
        SELECT 
            SUM(count) as vru_count
        FROM "vru-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s;
        """

        vehicle_results = self.db_client.execute_query(
            vehicle_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        speed_results = self.db_client.execute_query(
            speed_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )
        vru_results = self.db_client.execute_query(
            vru_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        # Extract vehicle / turning counts
        vehicle_count = 0
        turning_count = 0
        if vehicle_results and vehicle_results[0]["vehicle_count"]:
            vehicle_count = int(vehicle_results[0]["vehicle_count"])
            turning_count = (
                int(vehicle_results[0]["turning_count"])
                if vehicle_results[0]["turning_count"]
                else 0
            )

        # Compute avg_speed, free_flow_speed, and speed_variance from speed_results
        def parse_midpoint(bin_label: str) -> float:
            try:
                if not bin_label:
                    return 0.0
                s = str(bin_label).replace(" mph", "").strip()
                parts = [p.strip() for p in s.split("-")]
                if len(parts) == 2:
                    return (float(parts[0]) + float(parts[1])) / 2.0
                return float(parts[0]) if parts[0] else 0.0
            except Exception:
                return 0.0

        total_count = 0
        weighted_speed_sum = 0.0
        speed_values = []
        if speed_results:
            for r in speed_results:
                bin_label = str(r.get("speed_interval"))
                bin_count = int(r.get("bin_count") or 0)
                midpoint = parse_midpoint(bin_label)
                total_count += bin_count
                weighted_speed_sum += midpoint * bin_count
                if bin_count > 0:
                    speed_values.extend([midpoint] * min(bin_count, 1000))

        avg_speed = (weighted_speed_sum / total_count) if total_count > 0 else 0.0
        free_flow_speed = (
            np.percentile(speed_values, 85) if len(speed_values) > 0 else 30.0
        )
        speed_variance = 0.0
        if total_count > 0:
            mean = avg_speed
            var_acc = 0.0
            for r in speed_results:
                midpoint = parse_midpoint(str(r.get("speed_interval")))
                bin_count = int(r.get("bin_count") or 0)
                var_acc += ((midpoint - mean) ** 2) * bin_count
            speed_variance = var_acc / total_count if total_count > 0 else 0.0

        # Extract VRU count
        vru_count = 0
        if vru_results and vru_results[0]["vru_count"]:
            vru_count = int(vru_results[0]["vru_count"])

        # If no vehicle data found and a short-name was provided, attempt reverse lookup
        if (
            not vehicle_results or not vehicle_results[0]["vehicle_count"]
        ) and isinstance(intersection_id, str):
            try:
                full_name = reverse_lookup_intersection(intersection_id, self.db_client)
                if full_name and full_name != intersection_id:
                    vehicle_results_full = self.db_client.execute_query(
                        vehicle_query,
                        {
                            "intersection_id": full_name,
                            "start_time": start_time_us,
                            "end_time": end_time_us,
                        },
                    )
                    if (
                        vehicle_results_full
                        and vehicle_results_full[0]["vehicle_count"]
                    ):
                        vehicle_count = int(vehicle_results_full[0]["vehicle_count"])
                        turning_count = (
                            int(vehicle_results_full[0]["turning_count"])
                            if vehicle_results_full[0]["turning_count"]
                            else 0
                        )
                    # try to fetch speed/vru using full_name if needed
                    speed_results_full = self.db_client.execute_query(
                        speed_query,
                        {
                            "intersection_id": full_name,
                            "start_time": start_time_us,
                            "end_time": end_time_us,
                        },
                    )
                    if speed_results_full:
                        total_count = 0
                        weighted_speed_sum = 0.0
                        speed_values = []
                        for r in speed_results_full:
                            bin_label = str(r.get("speed_interval"))
                            bin_count = int(r.get("bin_count") or 0)
                            midpoint = parse_midpoint(bin_label)
                            total_count += bin_count
                            weighted_speed_sum += midpoint * bin_count
                            if bin_count > 0:
                                speed_values.extend([midpoint] * min(bin_count, 1000))
                        avg_speed = (
                            (weighted_speed_sum / total_count)
                            if total_count > 0
                            else avg_speed
                        )
                        free_flow_speed = (
                            np.percentile(speed_values, 85)
                            if len(speed_values) > 0
                            else free_flow_speed
                        )
                        if total_count > 0:
                            mean = avg_speed
                            var_acc = 0.0
                            for r in speed_results_full:
                                midpoint = parse_midpoint(str(r.get("speed_interval")))
                                bin_count = int(r.get("bin_count") or 0)
                                var_acc += ((midpoint - mean) ** 2) * bin_count
                            speed_variance = (
                                var_acc / total_count
                                if total_count > 0
                                else speed_variance
                            )
                    vru_results_full = self.db_client.execute_query(
                        vru_query,
                        {
                            "intersection_id": full_name,
                            "start_time": start_time_us,
                            "end_time": end_time_us,
                        },
                    )
                    if vru_results_full and vru_results_full[0]["vru_count"]:
                        vru_count = int(vru_results_full[0]["vru_count"])
            except Exception:
                pass

        # Log computed speed and counts for debugging
        logger.info(
            f"RT-SI: computed traffic for {intersection_id} at {timestamp.isoformat()}: "
            f"vehicle_count={vehicle_count}, vru_count={vru_count}, turning_count={turning_count}, "
            f"avg_speed={avg_speed:.2f}, speed_variance={speed_variance:.4f}, free_flow_speed={free_flow_speed:.2f}"
        )

        return {
            "vehicle_count": vehicle_count,
            "turning_count": turning_count,
            "vru_count": vru_count,
            "avg_speed": avg_speed,
            "speed_variance": speed_variance,
            "free_flow_speed": free_flow_speed,
        }

    def get_realtime_data(
        self,
        intersection_id,
        timestamp: datetime,
        bin_minutes: int = 15,
        lookback_hours: int = 24,
    ) -> Dict:
        """
        Get real-time traffic data for the given time bin.
        If no data available at the exact timestamp, looks back to find a previous bin with data.

        Args:
            intersection_id: Can be int (crash intersection ID) or str (BSM intersection name)
            timestamp: Time to query data for
            bin_minutes: Time bin size in minutes
            lookback_hours: Maximum hours to look back for data if exact timestamp unavailable (default: 168 = 1 week)

        Returns dict with:
        - vehicle_count: number of vehicles
        - turning_count: number of turning vehicles
        - vru_count: number of VRUs
        - avg_speed: average speed
        - speed_variance: variance in speed
        - free_flow_speed: free-flow speed (85th percentile)
        """

        # Normalize to short-name for real-time tables
        intersection_identifier = self._to_short_name(intersection_id)

        # OPTIMIZATION: Find the latest available data timestamp within lookback window
        # in a single query instead of checking each bin sequentially
        lookback_limit = timestamp - timedelta(hours=lookback_hours)
        lookback_limit_us = int(lookback_limit.timestamp() * 1000000)
        timestamp_us = int(timestamp.timestamp() * 1000000)

        latest_data_query = """
        SELECT MAX(publish_timestamp) as latest_ts
        FROM "vehicle-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(lookback_limit)s
          AND publish_timestamp <= %(timestamp)s;
        """

        latest_result = self.db_client.execute_query(
            latest_data_query,
            {
                "intersection_id": intersection_identifier,
                "lookback_limit": lookback_limit_us,
                "timestamp": timestamp_us,
            },
        )

        if not latest_result or not latest_result[0]["latest_ts"]:
            # No data found within lookback window
            logger.warning(
                f"No data found for intersection {intersection_id} within {lookback_hours} hours of {timestamp}. "
                "Returning empty data."
            )
            return {
                "vehicle_count": 0,
                "turning_count": 0,
                "vru_count": 0,
                "avg_speed": 0.0,
                "speed_variance": 0.0,
                "free_flow_speed": 30.0,
            }

        # Find the time bin that contains the latest data
        latest_ts_us = latest_result[0]["latest_ts"]
        latest_ts = datetime.fromtimestamp(latest_ts_us / 1000000)

        # Align to bin boundaries
        bin_microseconds = bin_minutes * 60 * 1000000
        bin_start_us = (latest_ts_us // bin_microseconds) * bin_microseconds
        current_timestamp = datetime.fromtimestamp(bin_start_us / 1000000)

        if current_timestamp != timestamp:
            hours_back = (timestamp - current_timestamp).total_seconds() / 3600
            logger.info(
                f"No data at {timestamp}, using data from time bin starting at {current_timestamp} "
                f"({hours_back:.1f} hours earlier)"
            )

        # Calculate bin time range for queries
        end_time = current_timestamp + timedelta(minutes=bin_minutes)
        start_time_us = int(current_timestamp.timestamp() * 1000000)
        end_time_us = int(end_time.timestamp() * 1000000)

        # Query vehicle count and turning movements
        vehicle_query = """
        SELECT 
            SUM(count) as vehicle_count,
            SUM(CASE WHEN movement IN ('LT', 'RT', 'UT') THEN count ELSE 0 END) as turning_count
        FROM "vehicle-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s;
        """

        # Query speed distribution for avg speed and variance
        speed_query = """
        WITH speed_data AS (
            SELECT 
                speed_interval,
                SUM(count) as bin_count
            FROM "speed-distribution"
            WHERE intersection = %(intersection_id)s::text
              AND publish_timestamp >= %(start_time)s
              AND publish_timestamp < %(end_time)s
            GROUP BY speed_interval
        )
        SELECT 
            SUM(bin_count) as total_count,
            SUM(
                (CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 1), ' ', 1) AS FLOAT) + 
                 CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 2), ' ', 1) AS FLOAT)) / 2.0 * bin_count
            ) / NULLIF(SUM(bin_count), 0) as avg_speed,
            PERCENTILE_CONT(0.85) WITHIN GROUP (
                ORDER BY (CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 1), ' ', 1) AS FLOAT) + 
                         CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 2), ' ', 1) AS FLOAT)) / 2.0
            ) as free_flow_speed
        FROM speed_data;
        """

        # Query VRU count
        vru_query = """
        SELECT 
            SUM(count) as vru_count
        FROM "vru-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s;
        """

        vehicle_results = self.db_client.execute_query(
            vehicle_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        speed_results = self.db_client.execute_query(
            speed_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )
        vru_results = self.db_client.execute_query(
            vru_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )
        # Extract vehicle / turning counts
        vehicle_count = 0
        turning_count = 0
        if vehicle_results and vehicle_results[0]["vehicle_count"]:
            vehicle_count = int(vehicle_results[0]["vehicle_count"])
            turning_count = (
                int(vehicle_results[0]["turning_count"])
                if vehicle_results[0]["turning_count"]
                else 0
            )
        free_flow_speed = 30.0  # Default
        speed_variance = 0.0

        if speed_results and speed_results[0]["total_count"]:
            speed_row = speed_results[0]
            avg_speed = float(speed_row["avg_speed"]) if speed_row["avg_speed"] else 0.0
            free_flow_speed = (
                float(speed_row["free_flow_speed"])
                if speed_row["free_flow_speed"]
                else 30.0
            )
            # Approximate variance from speed distribution
            # (simplified: using 10% of avg_speed as std dev)
            speed_variance = (avg_speed * 0.1) ** 2

        # Extract VRU count
        vru_count = 0
        if vru_results and vru_results[0]["vru_count"]:
            vru_count = int(vru_results[0]["vru_count"])

        return {
            "vehicle_count": vehicle_count,
            "turning_count": turning_count,
            "vru_count": vru_count,
            "avg_speed": avg_speed,
            "speed_variance": speed_variance,
            "free_flow_speed": free_flow_speed,
        }

    def compute_uplift_factors(
        self,
        avg_speed: float,
        free_flow_speed: float,
        speed_variance: float,
        vehicle_count: int,
        vru_count: int,
        turning_count: int = 0,
    ) -> Dict:
        """
        Compute real-time uplift factors.

        Args:
            avg_speed: Average speed in mph
            free_flow_speed: Free-flow speed (85th percentile) in mph
            speed_variance: Variance in speed
            vehicle_count: Total vehicle count
            vru_count: VRU (pedestrian/cyclist) count
            turning_count: Number of turning vehicles (LT, RT, UT)

        Returns dict with F_speed, F_variance, F_conflict, and combined U.
        """
        epsilon = 1e-6

        # Speed reduction factor: more congestion = higher risk
        speed_reduction = max(0, free_flow_speed - avg_speed)
        F_speed = min(
            1.0,
            self.K1_SPEED * (speed_reduction / (free_flow_speed + epsilon)),
        )

        # Speed variance factor: more variation = higher risk
        F_variance = min(
            1.0, self.K2_VAR * (np.sqrt(speed_variance) / (avg_speed + epsilon))
        )

        # Conflict factor: turning vehicles crossing VRU paths = higher risk
        # Use actual turning count from vehicle-count table (LT, RT, UT movements)
        conflict_exposure = turning_count * vru_count
        F_conflict = min(1.0, self.K3_CONF * (conflict_exposure / 1000.0))

        # Combined uplift factor
        U = (
            1.0
            + self.BETA1 * F_speed
            + self.BETA2 * F_variance
            + self.BETA3 * F_conflict
        )

        return {
            "F_speed": F_speed,
            "F_variance": F_variance,
            "F_conflict": F_conflict,
            "U": U,
        }

    def compute_sub_indices(
        self,
        r_hat: float,
        U: float,
        vehicle_count: int,
        vru_count: int,
        capacity: float,
    ) -> Dict:
        """
        Compute VRU and Vehicle sub-indices.

        Returns dict with VRU_index and VEH_index.
        """
        epsilon = 1e-6

        # VRU exposure ratio
        G = min(1.0, self.K4_VRU_RATIO * (vru_count / (vehicle_count + epsilon)))

        # VRU sub-index
        VRU_index = self.GAMMA * r_hat * U * G

        # Vehicle congestion ratio
        H = min(1.0, self.K5_VOL_CAPACITY * (vehicle_count / capacity))

        # Vehicle sub-index
        VEH_index = self.GAMMA * r_hat * U * H

        return {
            "G": G,
            "VRU_index": VRU_index,
            "H": H,
            "VEH_index": VEH_index,
        }

    def compute_combined_index(self, VRU_index: float, VEH_index: float) -> float:
        """
        Compute combined index as weighted sum of VRU and Vehicle indices.
        """
        COMB = self.OMEGA_VRU * VRU_index + self.OMEGA_VEH * VEH_index
        return COMB

    def scale_to_100(
        self, COMB: float, min_val: float = 0.0, max_val: float = 1.0
    ) -> float:
        """
        Scale combined index to 0-100 range.

        Note: min and max should be computed from historical data distribution.
        For now, using simple scaling.
        """
        if max_val - min_val == 0:
            return 0.0

        # Invert scale: lower COMB = higher safety
        # Higher risk index → lower safety score
        scaled = 100.0 * (1.0 - (COMB - min_val) / (max_val - min_val))
        return max(0.0, min(100.0, scaled))  # Clamp to 0-100

    def calculate_rt_si(
        self,
        intersection_id: int,
        timestamp: datetime,
        bin_minutes: int = 15,
        realtime_intersection: Optional[str] = None,
        lookback_hours: int = 24,
    ) -> Optional[Dict]:
        """
        Calculate Real-Time Safety Index for an intersection at a given time.
        If no data available at the exact timestamp, looks back up to lookback_hours for latest data.

        Args:
            intersection_id: Crash intersection ID for historical data
            timestamp: Time to calculate RT-SI for
            bin_minutes: Time bin size in minutes
            realtime_intersection: Optional string intersection name for real-time data
                                  (e.g., 'glebe-potomac'). If None, uses intersection_id.
            lookback_hours: Maximum hours to look back for data if exact timestamp unavailable (default: 168 = 1 week)

        Returns dict with all components of RT-SI calculation.
        """
        try:
            # Step 1: Get historical crash rate (year-only)
            hist_data = self.get_historical_crash_rate(intersection_id)
            raw_rate = hist_data["raw_rate"]
            exposure = hist_data["exposure"]

            # Step 2: Empirical Bayes stabilization
            r_hat = self.compute_eb_rate(raw_rate, exposure)

            # Step 3: Get real-time data
            # Use realtime_intersection if provided, otherwise use intersection_id
            rt_intersection = (
                realtime_intersection if realtime_intersection else intersection_id
            )
            logger.info(
                f"RT-SI: resolved realtime_intersection for DB queries: {repr(rt_intersection)}"
            )
            rt_data = self.get_realtime_data(
                rt_intersection, timestamp, bin_minutes, lookback_hours
            )
            logger.info(
                f"RT-SI: realtime data for {repr(rt_intersection)} at {timestamp.isoformat()}: {rt_data}"
            )

            # Note: We now allow zero traffic counts to proceed with calculation
            # This ensures all time bins in a range have RT-SI values, even if traffic is zero

            # Step 4: Compute intersection capacity from historical data
            capacity = self.get_intersection_capacity(
                rt_intersection, bin_minutes=bin_minutes, lookback_days=30
            )
            logger.info(
                f"RT-SI: computed capacity for {repr(rt_intersection)}: {capacity} vehicles per {bin_minutes}min"
            )

            # Log key realtime values before uplift/sub-index calculations
            try:
                logger.info(
                    "RT-SI: pre-compute values: "
                    f"vehicle_count={rt_data.get('vehicle_count')}, "
                    f"vru_count={rt_data.get('vru_count')}, "
                    f"avg_speed={rt_data.get('avg_speed')}, "
                    f"speed_variance={rt_data.get('speed_variance')}, "
                    f"turning_count={rt_data.get('turning_count')}"
                )
            except Exception:
                logger.debug("RT-SI: could not log pre-compute realtime values")

            # Step 5: Compute uplift factors
            uplift = self.compute_uplift_factors(
                rt_data["avg_speed"],
                rt_data["free_flow_speed"],
                rt_data["speed_variance"],
                rt_data["vehicle_count"],
                rt_data["vru_count"],
                rt_data["turning_count"],  # Use actual turning movements from data
            )

            # Step 6: Compute sub-indices
            sub_indices = self.compute_sub_indices(
                r_hat,
                uplift["U"],
                rt_data["vehicle_count"],
                rt_data["vru_count"],
                capacity,  # Use computed capacity instead of default
            )

            # Step 7: Compute combined index
            COMB = self.compute_combined_index(
                sub_indices["VRU_index"], sub_indices["VEH_index"]
            )

            # Step 8: Cap the combined index at 100
            # COMB represents risk level, we cap it at 100 for the safety index scale
            RT_SI = min(100.0, COMB)

            result = {
                "intersection_id": intersection_id,
                "timestamp": timestamp.isoformat(),
                "time_bin_minutes": bin_minutes,
                # Historical data
                "historical_crashes": hist_data["weighted_crashes"],
                "historical_exposure": exposure,
                "raw_crash_rate": raw_rate,
                "eb_crash_rate": r_hat,
                # Real-time data
                "vehicle_count": rt_data["vehicle_count"],
                "vru_count": rt_data["vru_count"],
                "avg_speed": rt_data["avg_speed"],
                "speed_variance": rt_data["speed_variance"],
                "free_flow_speed": rt_data["free_flow_speed"],
                # Uplift factors
                "F_speed": uplift["F_speed"],
                "F_variance": uplift["F_variance"],
                "F_conflict": uplift["F_conflict"],
                "uplift_factor": uplift["U"],
                # Sub-indices
                "VRU_exposure_ratio": sub_indices["G"],
                "VRU_index": sub_indices["VRU_index"],
                "vehicle_congestion_ratio": sub_indices["H"],
                "VEH_index": sub_indices["VEH_index"],
                # Final index
                "combined_index": COMB,
                "RT_SI": RT_SI,
                "safety_score": RT_SI,  # Alias for compatibility
            }

            return result

        except Exception as e:
            logger.error(
                f"Error calculating RT-SI for intersection {intersection_id}: {e}",
                exc_info=True,
            )
            return None

    def get_bulk_traffic_data(
        self,
        intersection_id,
        start_time: datetime,
        end_time: datetime,
        bin_minutes: int = 15,
    ) -> Dict[datetime, Dict]:
        """
        Get traffic data for all time bins in a range using batched queries.
        Much faster than querying each time bin individually.

        Returns dict mapping timestamp -> traffic data
        """
        start_time_us = int(start_time.timestamp() * 1000000)
        end_time_us = int(end_time.timestamp() * 1000000)
        bin_microseconds = bin_minutes * 60 * 1000000

        # Normalize to short-name for real-time tables
        intersection_identifier = self._to_short_name(intersection_id)

        # Single query for all vehicle data, grouped by time bin
        vehicle_query = """
        SELECT 
            ((publish_timestamp - %(start_time)s) / %(bin_us)s) * %(bin_us)s + %(start_time)s as time_bin,
            SUM(count) as vehicle_count,
            SUM(CASE WHEN movement IN ('LT', 'RT', 'UT') THEN count ELSE 0 END) as turning_count
        FROM "vehicle-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s
        GROUP BY time_bin
        ORDER BY time_bin;
        """

        # Single query for all speed data, grouped by time bin
        # Handle both "X-Y mph" ranges and "X+" format (e.g., "91+")
        speed_query = """
        WITH binned_speed AS (
            SELECT 
                ((publish_timestamp - %(start_time)s) / %(bin_us)s) * %(bin_us)s + %(start_time)s as time_bin,
                speed_interval,
                SUM(count) as bin_count,
                -- Parse speed value handling both "X-Y" and "X+" formats
                CASE 
                    WHEN speed_interval LIKE '%%+%%' THEN 
                        -- For "91+" format, use the number as midpoint (treat as 91-100)
                        CAST(REGEXP_REPLACE(speed_interval, '[^0-9]', '', 'g') AS FLOAT) + 5.0
                    ELSE
                        -- For "X-Y mph" format, calculate midpoint
                        (CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 1), ' ', 1) AS FLOAT) + 
                         CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 2), ' ', 1) AS FLOAT)) / 2.0
                END as speed_midpoint
            FROM "speed-distribution"
            WHERE intersection = %(intersection_id)s::text
              AND publish_timestamp >= %(start_time)s
              AND publish_timestamp < %(end_time)s
            GROUP BY time_bin, speed_interval
        )
        SELECT 
            time_bin,
            SUM(bin_count) as total_count,
            SUM(speed_midpoint * bin_count) / NULLIF(SUM(bin_count), 0) as avg_speed,
            PERCENTILE_CONT(0.85) WITHIN GROUP (ORDER BY speed_midpoint) as free_flow_speed
        FROM binned_speed
        GROUP BY time_bin
        ORDER BY time_bin;
        """

        # Single query for all VRU data, grouped by time bin
        vru_query = """
        SELECT 
            ((publish_timestamp - %(start_time)s) / %(bin_us)s) * %(bin_us)s + %(start_time)s as time_bin,
            SUM(count) as vru_count
        FROM "vru-count"
        WHERE intersection = %(intersection_id)s::text
          AND publish_timestamp >= %(start_time)s
          AND publish_timestamp < %(end_time)s
        GROUP BY time_bin
        ORDER BY time_bin;
        """

        vehicle_results = self.db_client.execute_query(
            vehicle_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
                "bin_us": bin_microseconds,
            },
        )
        logger.info(f"Vehicle data: {len(vehicle_results)} time bins")

        speed_results = self.db_client.execute_query(
            speed_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
                "bin_us": bin_microseconds,
            },
        )
        logger.info(f"Speed data: {len(speed_results)} time bins")

        vru_results = self.db_client.execute_query(
            vru_query,
            {
                "intersection_id": intersection_identifier,
                "start_time": start_time_us,
                "end_time": end_time_us,
                "bin_us": bin_microseconds,
            },
        )
        logger.info(f"VRU data: {len(vru_results)} time bins")

        # Build lookup maps
        vehicle_map = {}
        for row in vehicle_results:
            time_bin_us = int(row["time_bin"])
            time_bin_dt = datetime.fromtimestamp(time_bin_us / 1000000)
            vehicle_map[time_bin_dt] = {
                "vehicle_count": (
                    int(row["vehicle_count"]) if row["vehicle_count"] else 0
                ),
                "turning_count": (
                    int(row["turning_count"]) if row["turning_count"] else 0
                ),
            }

        speed_map = {}
        for row in speed_results:
            time_bin_us = int(row["time_bin"])
            time_bin_dt = datetime.fromtimestamp(time_bin_us / 1000000)
            speed_map[time_bin_dt] = {
                "avg_speed": float(row["avg_speed"]) if row["avg_speed"] else 0.0,
                "free_flow_speed": (
                    float(row["free_flow_speed"]) if row["free_flow_speed"] else 30.0
                ),
                "speed_variance": (
                    (float(row["avg_speed"]) * 0.1) ** 2 if row["avg_speed"] else 0.0
                ),
            }

        vru_map = {}
        for row in vru_results:
            time_bin_us = int(row["time_bin"])
            time_bin_dt = datetime.fromtimestamp(time_bin_us / 1000000)
            vru_map[time_bin_dt] = {
                "vru_count": int(row["vru_count"]) if row["vru_count"] else 0
            }

        # Generate ALL time bins in range (not just those with data)
        result_map = {}
        current_time = start_time

        while current_time < end_time:
            # Check if we have vehicle data for this bin
            veh_data = vehicle_map.get(
                current_time, {"vehicle_count": 0, "turning_count": 0}
            )
            speed_data = speed_map.get(
                current_time,
                {
                    "avg_speed": 0.0,
                    "free_flow_speed": 30.0,
                    "speed_variance": 0.0,
                },
            )
            vru_data = vru_map.get(current_time, {"vru_count": 0})

            # Include ALL time bins, even with zero counts
            result_map[current_time] = {
                "vehicle_count": veh_data["vehicle_count"],
                "turning_count": veh_data["turning_count"],
                "vru_count": vru_data["vru_count"],
                **speed_data,
            }

            # Move to next time bin
            current_time += timedelta(minutes=bin_minutes)

        # Post-process: forward-fill short gaps of missing data so RT-SI does not
        # collapse to zero for intermittent empty bins. We consider a bin "empty"
        # when vehicle_count==0 and vru_count==0 and avg_speed==0.
        # Fill-forward is applied only for short gaps (default up to 1 hour)
        # to avoid inventing data over long periods.
        max_gap_bins = max(1, int(60 / bin_minutes))  # e.g., 4 bins for 15-min

        sorted_bins = sorted(result_map.keys())
        last_seen = None
        last_seen_idx = None

        for idx, t in enumerate(sorted_bins):
            bin_row = result_map[t]
            is_empty = (
                (bin_row.get("vehicle_count", 0) == 0)
                and (bin_row.get("vru_count", 0) == 0)
                and (bin_row.get("avg_speed", 0.0) == 0.0)
            )

            if not is_empty:
                # Update last seen non-empty observation
                last_seen = dict(bin_row)
                last_seen_idx = idx
                # Ensure a small variance floor if avg_speed > 0 but variance is zero
                if (
                    last_seen.get("avg_speed", 0.0) > 0
                    and last_seen.get("speed_variance", 0.0) <= 0.0
                ):
                    sigma_floor = max(1.0, last_seen["avg_speed"] * 0.05)
                    last_seen["speed_variance"] = sigma_floor * sigma_floor
                    bin_row["speed_variance"] = last_seen["speed_variance"]
            else:
                # Empty bin: try to fill from last_seen if gap is small
                if (
                    last_seen is not None
                    and last_seen_idx is not None
                    and (idx - last_seen_idx) <= max_gap_bins
                ):
                    # copy values from last_seen into current bin
                    filled = dict(last_seen)
                    # keep the timestamp-specific fields as-is
                    filled["vehicle_count"] = last_seen.get("vehicle_count", 0)
                    filled["turning_count"] = last_seen.get("turning_count", 0)
                    filled["vru_count"] = last_seen.get("vru_count", 0)
                    filled["avg_speed"] = last_seen.get("avg_speed", 0.0)
                    filled["speed_variance"] = last_seen.get("speed_variance", 0.0)
                    filled["free_flow_speed"] = last_seen.get("free_flow_speed", 30.0)
                    result_map[t] = filled
                    logger.debug(
                        f"Filled empty bin {t} with last seen data from {sorted_bins[last_seen_idx]}"
                    )
                else:
                    # Leave empty bin as-is, but ensure a tiny variance floor to avoid divide-by-zero
                    if (
                        bin_row.get("avg_speed", 0.0) > 0
                        and bin_row.get("speed_variance", 0.0) <= 0.0
                    ):
                        sigma_floor = max(0.5, bin_row["avg_speed"] * 0.03)
                        bin_row["speed_variance"] = sigma_floor * sigma_floor

        return result_map

    def calculate_rt_si_trend(
        self,
        intersection_id: int,
        start_time: datetime,
        end_time: datetime,
        bin_minutes: int = 15,
        realtime_intersection: Optional[str] = None,
    ) -> List[Dict]:
        """
        Calculate RT-SI trend over a time range.
        OPTIMIZED: Uses bulk query to fetch all data at once instead of per-bin queries.

        Args:
            intersection_id: Crash intersection ID for historical data
            start_time: Start of time range
            end_time: End of time range
            bin_minutes: Time bin size in minutes
            realtime_intersection: Optional BSM intersection name for real-time data

        Returns list of RT-SI calculations for each time bin with data.
        """
        results = []

        # Calculate capacity once for all time bins (doesn't change per bin)
        rt_intersection = (
            realtime_intersection if realtime_intersection else intersection_id
        )
        capacity = self.get_intersection_capacity(
            rt_intersection, bin_minutes=bin_minutes, lookback_days=30
        )

        # OPTIMIZATION: Get ALL traffic data at once with bulk query
        logger.info(f"Fetching bulk traffic data from {start_time} to {end_time}")
        traffic_data_map = self.get_bulk_traffic_data(
            rt_intersection, start_time, end_time, bin_minutes
        )
        logger.info(f"Retrieved data for {len(traffic_data_map)} time bins")

        # Count bins with actual traffic data
        bins_with_data = sum(
            1
            for v in traffic_data_map.values()
            if v.get("vehicle_count", 0) > 0
            or v.get("vru_count", 0) > 0
            or v.get("avg_speed", 0) > 0
        )
        logger.info(
            f"Time bins with actual traffic data: {bins_with_data}/{len(traffic_data_map)}"
        )

        # Use year-only historical crash rate (same for all bins)
        hist_data = self.get_historical_crash_rate(intersection_id)
        raw_rate = hist_data["raw_rate"]
        exposure = hist_data["exposure"]
        r_hat = self.compute_eb_rate(raw_rate, exposure)

        # Process each time bin that has data
        for current_time, rt_data in sorted(traffic_data_map.items()):
            try:

                # Compute uplift factors
                uplift = self.compute_uplift_factors(
                    rt_data["avg_speed"],
                    rt_data["free_flow_speed"],
                    rt_data["speed_variance"],
                    rt_data["vehicle_count"],
                    rt_data["vru_count"],
                    rt_data["turning_count"],
                )

                # Compute sub-indices
                sub_indices = self.compute_sub_indices(
                    r_hat,
                    uplift["U"],
                    rt_data["vehicle_count"],
                    rt_data["vru_count"],
                    capacity,
                )

                # Compute combined index
                COMB = self.compute_combined_index(
                    sub_indices["VRU_index"], sub_indices["VEH_index"]
                )

                # Cap at 100
                RT_SI = min(100.0, COMB)

                result = {
                    "intersection_id": intersection_id,
                    "timestamp": current_time.isoformat(),
                    "time_bin_minutes": bin_minutes,
                    "historical_crashes": hist_data["weighted_crashes"],
                    "historical_exposure": exposure,
                    "raw_crash_rate": raw_rate,
                    "eb_crash_rate": r_hat,
                    "vehicle_count": rt_data["vehicle_count"],
                    "vru_count": rt_data["vru_count"],
                    "avg_speed": rt_data["avg_speed"],
                    "speed_variance": rt_data["speed_variance"],
                    "free_flow_speed": rt_data["free_flow_speed"],
                    "F_speed": uplift["F_speed"],
                    "F_variance": uplift["F_variance"],
                    "F_conflict": uplift["F_conflict"],
                    "uplift_factor": uplift["U"],
                    "VRU_exposure_ratio": sub_indices["G"],
                    "VRU_index": sub_indices["VRU_index"],
                    "vehicle_congestion_ratio": sub_indices["H"],
                    "VEH_index": sub_indices["VEH_index"],
                    "combined_index": COMB,
                    "RT_SI": RT_SI,
                    "safety_score": RT_SI,
                }

                results.append(result)

            except Exception as e:
                logger.error(
                    f"Error calculating RT-SI for time bin {current_time}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Calculated RT-SI trend for intersection {intersection_id}: "
            f"{len(results)} time bins processed, {len(results)} results from {start_time} to {end_time}"
        )

        return results

    def calculate_rt_si_from_data(
        self,
        intersection_id: int,
        traffic_data_map: Dict[datetime, Dict],
        capacity: float,
        bin_minutes: int = 15,
    ) -> List[Dict]:
        """
        Calculate RT-SI scores from pre-fetched traffic data.
        Used for sensitivity analysis to avoid repeated DB queries.

        Args:
            intersection_id: Crash intersection ID
            traffic_data_map: Dict mapping timestamp -> traffic data
            capacity: Intersection capacity
            bin_minutes: Time bin size

        Returns:
            List of RT-SI result dicts
        """
        results = []

        # Use year-only historical crash rate for all bins
        hist_data = self.get_historical_crash_rate(intersection_id)
        raw_rate = hist_data["raw_rate"]
        exposure = hist_data["exposure"]
        r_hat = self.compute_eb_rate(raw_rate, exposure)

        for current_time, rt_data in sorted(traffic_data_map.items()):
            try:

                # Compute uplift factors
                uplift = self.compute_uplift_factors(
                    rt_data["avg_speed"],
                    rt_data["free_flow_speed"],
                    rt_data["speed_variance"],
                    rt_data["vehicle_count"],
                    rt_data["vru_count"],
                    rt_data["turning_count"],
                )

                # Compute sub-indices
                sub_indices = self.compute_sub_indices(
                    r_hat,
                    uplift["U"],
                    rt_data["vehicle_count"],
                    rt_data["vru_count"],
                    capacity,
                )

                # Compute combined index
                COMB = self.compute_combined_index(
                    sub_indices["VRU_index"], sub_indices["VEH_index"]
                )

                # Cap at 100
                RT_SI = min(100.0, COMB)

                result = {
                    "intersection_id": intersection_id,
                    "timestamp": current_time.isoformat(),
                    "time_bin_minutes": bin_minutes,
                    "historical_crashes": hist_data["weighted_crashes"],
                    "historical_exposure": exposure,
                    "raw_crash_rate": raw_rate,
                    "eb_crash_rate": r_hat,
                    "vehicle_count": rt_data["vehicle_count"],
                    "vru_count": rt_data["vru_count"],
                    "avg_speed": rt_data["avg_speed"],
                    "speed_variance": rt_data["speed_variance"],
                    "free_flow_speed": rt_data["free_flow_speed"],
                    "F_speed": uplift["F_speed"],
                    "F_variance": uplift["F_variance"],
                    "F_conflict": uplift["F_conflict"],
                    "uplift_factor": uplift["U"],
                    "VRU_exposure_ratio": sub_indices["G"],
                    "VRU_index": sub_indices["VRU_index"],
                    "vehicle_congestion_ratio": sub_indices["H"],
                    "VEH_index": sub_indices["VEH_index"],
                    "combined_index": COMB,
                    "RT_SI": RT_SI,
                    "safety_score": RT_SI,
                }

                results.append(result)

            except Exception as e:
                logger.warning(
                    f"Error calculating RT-SI for time bin {current_time}: {e}"
                )

        return results


def main():
    """Test RT-SI calculation."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    db_client = VTTIPostgresClient()

    try:
        service = RTSIService(db_client)

        # Test with a specific intersection and time
        test_intersection = 1  # Replace with actual intersection ID
        test_time = datetime(2024, 11, 15, 10, 0)  # Example time

        print("\n" + "=" * 60)
        print("Testing RT-SI Calculation")
        print("=" * 60)
        print(f"Intersection ID: {test_intersection}")
        print(f"Timestamp: {test_time}")
        print()

        result = service.calculate_rt_si(test_intersection, test_time)

        if result:
            print("RT-SI CALCULATION RESULTS:")
            print("-" * 60)
            print(f"RT-SI Score:              {result['RT_SI']:.2f}")
            print(f"EB Crash Rate:            {result['eb_crash_rate']:.6f}")
            print(f"Uplift Factor:            {result['uplift_factor']:.3f}")
            print(f"  - Speed Factor:         {result['F_speed']:.3f}")
            print(f"  - Variance Factor:      {result['F_variance']:.3f}")
            print(f"  - Conflict Factor:      {result['F_conflict']:.3f}")
            print(f"VRU Index:                {result['VRU_index']:.6f}")
            print(f"Vehicle Index:            {result['VEH_index']:.6f}")
            print(f"Combined Index:           {result['combined_index']:.6f}")
            print(f"Vehicle Count:            {result['vehicle_count']}")
            print(f"VRU Count:                {result['vru_count']}")
            print(f"Avg Speed:                {result['avg_speed']:.1f} mph")
            print("-" * 60)
        else:
            print("❌ No result returned")

        print("=" * 60)

    finally:
        db_client.close()


if __name__ == "__main__":
    main()
