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

from app.services.db_client import VTTIPostgresClient

logger = logging.getLogger(__name__)


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

    def get_historical_crash_rate(
        self, intersection_id: int, hour: int, dow: int
    ) -> Dict:
        """
        Get historical severity-weighted crash rate for intersection-time bin.

        Returns dict with:
        - weighted_crashes: severity-weighted crash count
        - exposure: total vehicle volume
        - raw_rate: crashes per vehicle
        """
        query = """
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
          AND FLOOR(crash_military_time / 100) = %(hour)s
          AND EXTRACT(DOW FROM TO_DATE(crash_date::TEXT, 'YYYY-MM-DD')) = %(dow)s
          AND crash_year BETWEEN 2017 AND 2024;
        """

        results = self.db_client.execute_query(
            query,
            {
                "intersection_id": intersection_id,
                "hour": hour,
                "dow": dow,
                "w_fatal": self.W_FATAL,
                "w_injury": self.W_INJURY,
                "w_pdo": self.W_PDO,
            },
        )

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

            result = self.db_client.execute_query(
                capacity_query,
                {
                    "intersection_id": intersection_id,
                    "lookback_us": lookback_us,
                },
            )

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
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        speed_results = self.db_client.execute_query(
            speed_query,
            {
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        vru_results = self.db_client.execute_query(
            vru_query,
            {
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        # Extract results
        vehicle_count = 0
        turning_count = 0
        if vehicle_results and vehicle_results[0]["vehicle_count"]:
            vehicle_count = int(vehicle_results[0]["vehicle_count"])
            turning_count = (
                int(vehicle_results[0]["turning_count"])
                if vehicle_results[0]["turning_count"]
                else 0
            )

        # If no vehicle data, return None to indicate no data for this time bin
        if vehicle_count == 0:
            return None

        avg_speed = 0.0
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

    def get_realtime_data(
        self,
        intersection_id,
        timestamp: datetime,
        bin_minutes: int = 15,
        lookback_hours: int = 168,
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
        # Try to find a time bin with data, starting from the requested timestamp
        # and looking back in bin_minutes increments
        current_timestamp = timestamp
        lookback_limit = timestamp - timedelta(hours=lookback_hours)

        while current_timestamp >= lookback_limit:
            end_time = current_timestamp + timedelta(minutes=bin_minutes)
            start_time_us = int(current_timestamp.timestamp() * 1000000)
            end_time_us = int(end_time.timestamp() * 1000000)

            # Check if data exists for this time bin
            check_query = """
            SELECT COUNT(*) as count
            FROM "vehicle-count"
            WHERE intersection = %(intersection_id)s::text
              AND publish_timestamp >= %(start_time)s
              AND publish_timestamp < %(end_time)s;
            """

            check_result = self.db_client.execute_query(
                check_query,
                {
                    "intersection_id": intersection_id,
                    "start_time": start_time_us,
                    "end_time": end_time_us,
                },
            )

            has_data = check_result and check_result[0]["count"] > 0

            if has_data:
                # Found a bin with data
                if current_timestamp != timestamp:
                    hours_back = (timestamp - current_timestamp).total_seconds() / 3600
                    logger.info(
                        f"No data at {timestamp}, using data from time bin {current_timestamp} to {end_time} "
                        f"({hours_back:.1f} hours earlier)"
                    )
                break

            # Move back one bin
            current_timestamp -= timedelta(minutes=bin_minutes)
        else:
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
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        speed_results = self.db_client.execute_query(
            speed_query,
            {
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        vru_results = self.db_client.execute_query(
            vru_query,
            {
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
            },
        )

        # Extract results
        vehicle_count = 0
        turning_count = 0
        if vehicle_results and vehicle_results[0]["vehicle_count"]:
            vehicle_count = int(vehicle_results[0]["vehicle_count"])
            turning_count = (
                int(vehicle_results[0]["turning_count"])
                if vehicle_results[0]["turning_count"]
                else 0
            )

        avg_speed = 0.0
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
            "turning_count": turning_count,  # Actual turning movements from data
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
        lookback_hours: int = 168,
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
            # Extract time bin features
            hour = timestamp.hour
            dow = timestamp.weekday()  # 0=Monday, 6=Sunday

            # Step 1: Get historical crash rate
            hist_data = self.get_historical_crash_rate(intersection_id, hour, dow)
            raw_rate = hist_data["raw_rate"]
            exposure = hist_data["exposure"]

            # Step 2: Empirical Bayes stabilization
            r_hat = self.compute_eb_rate(raw_rate, exposure)

            # Step 3: Get real-time data
            # Use realtime_intersection if provided, otherwise use intersection_id
            rt_intersection = (
                realtime_intersection if realtime_intersection else intersection_id
            )
            rt_data = self.get_realtime_data(
                rt_intersection, timestamp, bin_minutes, lookback_hours
            )

            # Check if we have sufficient data
            if rt_data["vehicle_count"] == 0 and rt_data["vru_count"] == 0:
                logger.warning(
                    f"No traffic data for intersection {intersection_id} at {timestamp}. "
                    "Cannot calculate meaningful RT-SI without exposure."
                )
                return None

            # Step 4: Compute intersection capacity from historical data
            capacity = self.get_intersection_capacity(
                rt_intersection, bin_minutes=bin_minutes, lookback_days=30
            )

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
        speed_query = """
        WITH binned_speed AS (
            SELECT 
                ((publish_timestamp - %(start_time)s) / %(bin_us)s) * %(bin_us)s + %(start_time)s as time_bin,
                speed_interval,
                SUM(count) as bin_count
            FROM "speed-distribution"
            WHERE intersection = %(intersection_id)s::text
              AND publish_timestamp >= %(start_time)s
              AND publish_timestamp < %(end_time)s
            GROUP BY time_bin, speed_interval
        )
        SELECT 
            time_bin,
            SUM(bin_count) as total_count,
            SUM(
                (CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 1), ' ', 1) AS FLOAT) + 
                 CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 2), ' ', 1) AS FLOAT)) / 2.0 * bin_count
            ) / NULLIF(SUM(bin_count), 0) as avg_speed,
            PERCENTILE_CONT(0.85) WITHIN GROUP (
                ORDER BY (CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 1), ' ', 1) AS FLOAT) + 
                         CAST(SPLIT_PART(SPLIT_PART(speed_interval, '-', 2), ' ', 1) AS FLOAT)) / 2.0
            ) as free_flow_speed
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
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
                "bin_us": bin_microseconds,
            },
        )

        speed_results = self.db_client.execute_query(
            speed_query,
            {
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
                "bin_us": bin_microseconds,
            },
        )

        vru_results = self.db_client.execute_query(
            vru_query,
            {
                "intersection_id": intersection_id,
                "start_time": start_time_us,
                "end_time": end_time_us,
                "bin_us": bin_microseconds,
            },
        )

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

        # Merge data
        result_map = {}
        for time_bin, veh_data in vehicle_map.items():
            if veh_data["vehicle_count"] > 0:  # Only include bins with vehicle data
                speed_data = speed_map.get(
                    time_bin,
                    {
                        "avg_speed": 0.0,
                        "free_flow_speed": 30.0,
                        "speed_variance": 0.0,
                    },
                )
                vru_data = vru_map.get(time_bin, {"vru_count": 0})
                result_map[time_bin] = {
                    "vehicle_count": veh_data["vehicle_count"],
                    "turning_count": veh_data["turning_count"],
                    "vru_count": vru_data["vru_count"],
                    **speed_data,
                }

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

        # Cache for historical crash rates (hour, dow) -> data
        hist_cache = {}

        # Process each time bin that has data
        for current_time, rt_data in sorted(traffic_data_map.items()):
            try:
                # Get or compute historical crash rate for this hour/dow
                hour = current_time.hour
                dow = current_time.weekday()
                cache_key = (hour, dow)

                if cache_key not in hist_cache:
                    hist_data = self.get_historical_crash_rate(
                        intersection_id, hour, dow
                    )
                    raw_rate = hist_data["raw_rate"]
                    exposure = hist_data["exposure"]
                    r_hat = self.compute_eb_rate(raw_rate, exposure)
                    hist_cache[cache_key] = {
                        "hist_data": hist_data,
                        "raw_rate": raw_rate,
                        "exposure": exposure,
                        "r_hat": r_hat,
                    }

                cached = hist_cache[cache_key]
                hist_data = cached["hist_data"]
                raw_rate = cached["raw_rate"]
                exposure = cached["exposure"]
                r_hat = cached["r_hat"]

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

        logger.info(
            f"Calculated RT-SI trend for intersection {intersection_id}: "
            f"{len(results)} time bins with data from {start_time} to {end_time}"
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
