"""
MCDM Safety Index Service

Provides MCDM-based safety index calculation using real-time database data.
Simplified version adapted from data-integration/mcdm_safety_index.py
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .db_client import VTTIPostgresClient

logger = logging.getLogger(__name__)
# Ensure INFO logs are shown for this module
logger.setLevel(logging.INFO)


class MCDMSafetyIndexService:
    """
    Multi-Criteria Decision Making (MCDM) Safety Index Calculator.

    Uses CRITIC method for weight calculation and hybrid MCDM approach
    combining SAW, EDAS, and CODAS methods.
    """

    def __init__(self, db_client: VTTIPostgresClient):
        """Initialize MCDM calculator with database client."""
        self.client = db_client
        self.criteria_list = [
            "vehicle_count",
            "vru_count",
            "avg_speed",
            "speed_variance",
            "incident_count",
        ]
        self.criterion_weights = None
        self.method_weights = None

    def calculate_latest_safety_scores(
        self, bin_minutes: int = 15, lookback_hours: int = 24
    ) -> List[Dict]:
        """
        Calculate safety scores for all intersections using latest available data.

        Args:
            bin_minutes: Time bin size in minutes (default: 15)
            lookback_hours: Hours of data to look back (default: 24)

        Returns:
            List of dictionaries with intersection names and safety scores
        """
        try:
            # Query the minimum of maximum timestamps across all tables
            # This ensures we have data from all sources (BSM, PSM, vehicle-count, VRU, speed, events)
            latest_query = """
            SELECT MIN(max_ts) as latest FROM (
                SELECT MAX(publish_timestamp) as max_ts FROM "vehicle-count"
                UNION ALL
                SELECT MAX(publish_timestamp) as max_ts FROM "vru-count"
                UNION ALL
                SELECT MAX(publish_timestamp) as max_ts FROM "speed-distribution"
                UNION ALL
                SELECT MAX(publish_timestamp) as max_ts FROM "safety-event"
            ) AS max_timestamps;
            """
            result = self.client.execute_query(latest_query)

            if not result or not result[0]["latest"]:
                logger.warning("No data found in any table")
                return []

            latest_timestamp = datetime.fromtimestamp(result[0]["latest"] / 1_000_000)
            logger.info(
                f"Latest common timestamp across all tables: {latest_timestamp}"
            )
            end_time = latest_timestamp
            start_time = latest_timestamp - timedelta(hours=lookback_hours)

            logger.info(
                f"Calculating MCDM safety scores from {start_time} to {end_time}"
            )

            # Collect data
            matrix = self._collect_data_matrix(start_time, end_time, bin_minutes)

            if len(matrix) == 0:
                logger.warning(f"No data available in the last {lookback_hours} hours")
                return []

            # Calculate MCDM scores
            results = self._calculate_hybrid_mcdm(matrix)

            # Get the most recent time bin for each intersection
            latest_results = (
                results.sort_values("time_bin", ascending=False)
                .groupby("intersection")
                .first()
                .reset_index()
            )

            # Convert to list of dictionaries
            output = []
            for _, row in latest_results.iterrows():
                output.append(
                    {
                        "intersection": row["intersection"],
                        "safety_score": float(row["Safety_Score"]),
                        "mcdm_index": float(row["MCDM_Safety_Index"]),
                        "vehicle_count": int(row["vehicle_count"]),
                        "vru_count": int(row["vru_count"]),
                        "incident_count": int(row["incident_count"]),
                        "near_miss_count": int(row.get("near_miss_count", 0)),
                        "time_bin": row["time_bin"],
                    }
                )

            logger.info(
                f"Successfully calculated safety scores for {len(output)} intersections"
            )
            return output

        except Exception as e:
            logger.error(f"Error calculating MCDM safety scores: {e}", exc_info=True)
            return []

    def _collect_data_matrix(
        self, start_time: datetime, end_time: datetime, bin_minutes: int
    ) -> pd.DataFrame:
        """Collect and aggregate data into criteria matrix."""
        # Convert timestamps to microseconds
        start_ts = int(start_time.timestamp() * 1_000_000)
        end_ts = int(end_time.timestamp() * 1_000_000)
        bin_microseconds = bin_minutes * 60 * 1_000_000

        # Collect vehicle count data (column is 'count', not 'vehicle_count')
        vehicle_query = f"""
        SELECT 
            intersection,
            FLOOR(publish_timestamp / {bin_microseconds}) * {bin_microseconds} as time_bin,
            SUM(count) as vehicle_count
        FROM "vehicle-count"
        WHERE publish_timestamp >= {start_ts} AND publish_timestamp < {end_ts}
        GROUP BY intersection, time_bin
        """
        vehicle_data = pd.DataFrame(self.client.execute_query(vehicle_query))

        if len(vehicle_data) == 0:
            return pd.DataFrame()

        # Collect VRU count data (column is 'count', not 'vru_count')
        vru_query = f"""
        SELECT 
            intersection,
            FLOOR(publish_timestamp / {bin_microseconds}) * {bin_microseconds} as time_bin,
            SUM(count) as vru_count
        FROM "vru-count"
        WHERE publish_timestamp >= {start_ts} AND publish_timestamp < {end_ts}
        GROUP BY intersection, time_bin
        """
        vru_data = pd.DataFrame(self.client.execute_query(vru_query))

        # Collect speed distribution data (column is 'speed_interval', use 'count')
        speed_query = f"""
        SELECT 
            intersection,
            FLOOR(publish_timestamp / {bin_microseconds}) * {bin_microseconds} as time_bin,
            speed_interval as speed_bin,
            count as event_count
        FROM "speed-distribution"
        WHERE publish_timestamp >= {start_ts} AND publish_timestamp < {end_ts}
        """
        speed_data = pd.DataFrame(self.client.execute_query(speed_query))

        # Collect incident data (use publish_timestamp, not timestamp)
        incident_query = f"""
        SELECT 
            intersection,
            FLOOR(publish_timestamp / {bin_microseconds}) * {bin_microseconds} as time_bin,
            COUNT(*) as incident_count
        FROM "safety-event"
        WHERE publish_timestamp >= {start_ts} AND publish_timestamp < {end_ts}
        GROUP BY intersection, time_bin
        """
        incident_data = pd.DataFrame(self.client.execute_query(incident_query))

        # Collect near miss data (NM-VRU or NM-VV)
        near_miss_query = f"""
        SELECT 
            intersection,
            FLOOR(publish_timestamp / {bin_microseconds}) * {bin_microseconds} as time_bin,
            COUNT(*) as near_miss_count
        FROM "safety-event"
        WHERE publish_timestamp >= {start_ts} AND publish_timestamp < {end_ts}
          AND event_type IN ('NM-VRU', 'NM-VV')
        GROUP BY intersection, time_bin
        """
        near_miss_data = pd.DataFrame(self.client.execute_query(near_miss_query))

        # Process speed data
        speed_stats = self._process_speed_distribution(speed_data)

        # Merge all data
        matrix = vehicle_data.merge(
            vru_data, on=["intersection", "time_bin"], how="outer"
        )
        if len(speed_stats) > 0:
            matrix = matrix.merge(
                speed_stats, on=["intersection", "time_bin"], how="outer"
            )
        if len(incident_data) > 0:
            matrix = matrix.merge(
                incident_data, on=["intersection", "time_bin"], how="outer"
            )
        if len(near_miss_data) > 0:
            matrix = matrix.merge(
                near_miss_data, on=["intersection", "time_bin"], how="outer"
            )

        # Fill missing values
        matrix = matrix.fillna(0)

        # Convert time_bin to datetime
        matrix["time_bin"] = pd.to_datetime(matrix["time_bin"], unit="us")

        return matrix

    def _process_speed_distribution(self, speed_data: pd.DataFrame) -> pd.DataFrame:
        """Extract avg_speed and speed_variance from speed distribution."""
        if len(speed_data) == 0:
            return pd.DataFrame()

        def extract_midpoint(speed_bin: str) -> float:
            """Extract midpoint from speed bin like '20-30 mph'."""
            try:
                parts = speed_bin.replace(" mph", "").split("-")
                if len(parts) == 2:
                    return (float(parts[0]) + float(parts[1])) / 2
                return 0.0
            except:
                return 0.0

        speed_data["midpoint"] = speed_data["speed_bin"].apply(extract_midpoint)

        # Calculate weighted average and variance
        stats = (
            speed_data.groupby(["intersection", "time_bin"])
            .apply(
                lambda x: pd.Series(
                    {
                        "avg_speed": np.average(
                            x["midpoint"], weights=x["event_count"]
                        ),
                        "speed_variance": np.average(
                            (
                                x["midpoint"]
                                - np.average(x["midpoint"], weights=x["event_count"])
                            )
                            ** 2,
                            weights=x["event_count"],
                        ),
                    }
                )
            )
            .reset_index()
        )

        return stats

    def _calculate_hybrid_mcdm(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate hybrid MCDM safety index."""
        result = data.copy()

        # Extract decision matrix
        matrix = result[self.criteria_list].values

        # Normalize matrix
        matrix_normalized = self._normalize_matrix(matrix)

        # Calculate CRITIC weights for criteria
        self.criterion_weights = self._calculate_critic_weights(matrix_normalized)

        # Calculate SAW, EDAS, CODAS scores
        result["SAW"] = self._calculate_saw(matrix_normalized)
        result["EDAS"] = self._calculate_edas(matrix_normalized)
        result["CODAS"] = self._calculate_codas(matrix_normalized)

        # Calculate CRITIC weights for methods
        method_matrix = result[["EDAS", "CODAS", "SAW"]].values
        self.method_weights = self._calculate_critic_weights(
            method_matrix, criteria=["EDAS", "CODAS", "SAW"]
        )

        # Calculate weighted MCDM index
        result["MCDM_Safety_Index"] = (
            self.method_weights["EDAS"] * result["EDAS"]
            + self.method_weights["CODAS"] * result["CODAS"]
            + self.method_weights["SAW"] * result["SAW"]
        )

        # Safety Score equals MCDM Index (no inversion)
        result["Safety_Score"] = result["MCDM_Safety_Index"]

        return result

    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """Normalize decision matrix using min-max normalization."""
        normalized = np.zeros_like(matrix, dtype=float)
        for j in range(matrix.shape[1]):
            col = matrix[:, j]
            min_val = np.min(col)
            max_val = np.max(col)
            if max_val - min_val > 0:
                normalized[:, j] = (col - min_val) / (max_val - min_val)
            else:
                normalized[:, j] = 0
        return normalized

    def _calculate_critic_weights(
        self, matrix: np.ndarray, criteria: List[str] = None
    ) -> Dict[str, float]:
        """Calculate CRITIC weights."""
        if criteria is None:
            criteria = self.criteria_list

        # Standard deviations
        std_devs = np.std(matrix, axis=0)

        # Correlation matrix
        corr_matrix = np.corrcoef(matrix, rowvar=False)

        # Conflict measures
        conflicts = np.sum(1 - corr_matrix, axis=1)

        # Information content
        info_content = std_devs * conflicts

        # Normalize to get weights
        total = np.sum(info_content)
        if total > 0:
            weights = info_content / total
        else:
            weights = np.ones(len(criteria)) / len(criteria)

        return dict(zip(criteria, weights))

    def _calculate_saw(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate SAW (Simple Additive Weighting) scores."""
        weights = np.array([self.criterion_weights[c] for c in self.criteria_list])
        scores = np.dot(matrix, weights)
        # Scale to 0-100
        return self._scale_to_100(scores)

    def _calculate_edas(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate EDAS (Evaluation based on Distance from Average Solution) scores."""
        avg_solution = np.mean(matrix, axis=0)

        # Positive and negative distances
        pda = np.maximum(0, (matrix - avg_solution) / avg_solution)
        nda = np.maximum(0, (avg_solution - matrix) / avg_solution)

        # Weighted sums
        weights = np.array([self.criterion_weights[c] for c in self.criteria_list])
        sp = np.dot(pda, weights)
        sn = np.dot(nda, weights)

        # Normalize
        sp_norm = sp / np.max(sp) if np.max(sp) > 0 else sp
        sn_norm = sn / np.max(sn) if np.max(sn) > 0 else sn

        # Appraisal scores
        scores = (sp_norm + (1 - sn_norm)) / 2

        return self._scale_to_100(scores)

    def _calculate_codas(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate CODAS (COmbinative Distance-based ASsessment) scores."""
        weights = np.array([self.criterion_weights[c] for c in self.criteria_list])
        weighted_matrix = matrix * weights

        # Negative-ideal solution
        nis = np.min(weighted_matrix, axis=0)

        # Euclidean and Taxicab distances
        euclidean = np.sqrt(np.sum((weighted_matrix - nis) ** 2, axis=1))
        taxicab = np.sum(np.abs(weighted_matrix - nis), axis=1)

        # Construct relative assessment matrix
        psi = euclidean[:, np.newaxis] - euclidean
        psi[psi == 0] = (taxicab[:, np.newaxis] - taxicab)[psi == 0]

        # Assessment scores
        scores = np.sum(psi, axis=1)

        return self._scale_to_100(scores)

    def _scale_to_100(self, scores: np.ndarray) -> np.ndarray:
        """Scale scores to 0-100 range."""
        min_score = np.min(scores)
        max_score = np.max(scores)
        if max_score - min_score > 0:
            return ((scores - min_score) / (max_score - min_score)) * 100
        return np.ones_like(scores) * 50

    def calculate_safety_score_for_time(
        self, intersection: str, target_time: datetime, bin_minutes: int = 15
    ) -> Optional[Dict]:
        """
        Calculate safety score for a specific intersection at a specific time.

        Args:
            intersection: Intersection name
            target_time: Target datetime
            bin_minutes: Time bin size in minutes (default: 15)

        Returns:
            Dictionary with safety score details or None if no data
        """
        try:
            # Floor to nearest bin
            bin_start = target_time.replace(
                minute=(target_time.minute // bin_minutes) * bin_minutes,
                second=0,
                microsecond=0,
            )
            bin_end = bin_start + timedelta(minutes=bin_minutes)

            # Collect data from 1 day before for CRITIC calculation
            lookback_start = bin_start - timedelta(days=1)

            logger.info(
                f"Calculating safety score for {intersection} at {bin_start} (lookback from {lookback_start})"
            )

            matrix = self._collect_data_matrix(lookback_start, bin_end, bin_minutes)

            if len(matrix) == 0:
                logger.warning(f"No data available for {intersection} at {bin_start}")
                return None

            # Filter to the specific intersection
            matrix = matrix[matrix["intersection"] == intersection]

            if len(matrix) == 0:
                logger.warning(
                    f"No data for intersection {intersection} at {bin_start}"
                )
                return None

            # Calculate MCDM scores
            results = self._calculate_hybrid_mcdm(matrix)

            # Filter to target time bin
            target_results = results[results["time_bin"] == bin_start]

            if len(target_results) == 0:
                logger.warning(
                    f"No results for {intersection} at target time {bin_start}"
                )
                return None

            row = target_results.iloc[0]

            return {
                "intersection": row["intersection"],
                "time_bin": row["time_bin"],
                "mcdm_index": float(row["MCDM_Safety_Index"]),
                "vehicle_count": int(row["vehicle_count"]),
                "vru_count": int(row["vru_count"]),
                "avg_speed": float(row["avg_speed"]),
                "speed_variance": float(row["speed_variance"]),
                "incident_count": int(row["incident_count"]),
                "near_miss_count": int(row.get("near_miss_count", 0)),
                "saw_score": float(row["SAW"]),
                "edas_score": float(row["EDAS"]),
                "codas_score": float(row["CODAS"]),
            }

        except Exception as e:
            logger.error(
                f"Error calculating safety score for {intersection} at {target_time}: {e}",
                exc_info=True,
            )
            return None

    def calculate_safety_score_trend(
        self,
        intersection: str,
        start_time: datetime,
        end_time: datetime,
        bin_minutes: int = 15,
    ) -> List[Dict]:
        """
        Calculate safety score trend for an intersection over a time period.

        Args:
            intersection: Intersection name
            start_time: Start datetime
            end_time: End datetime
            bin_minutes: Time bin size in minutes (default: 15)

        Returns:
            List of dictionaries with safety scores for each time bin
        """
        try:
            logger.info(
                f"Calculating safety score trend for {intersection} from {start_time} to {end_time}"
            )

            # Collect data from 1 day before start time for CRITIC calculation
            lookback_start = start_time - timedelta(days=1)

            matrix = self._collect_data_matrix(lookback_start, end_time, bin_minutes)

            if len(matrix) == 0:
                logger.warning(
                    f"No data available for {intersection} in period {start_time} to {end_time}"
                )
                return []

            # Filter to the specific intersection
            matrix = matrix[matrix["intersection"] == intersection]

            if len(matrix) == 0:
                logger.warning(
                    f"No data for intersection {intersection} in specified period"
                )
                return []

            # Calculate MCDM scores with error handling
            try:
                results = self._calculate_hybrid_mcdm(matrix)
            except Exception as e:
                logger.error(f"Error in MCDM calculation: {e}", exc_info=True)
                # Try processing time bins individually to skip problematic ones
                return self._calculate_trend_individually(
                    matrix, start_time, end_time, intersection
                )

            # Filter to requested time range (excluding lookback data)
            results = results[
                (results["time_bin"] >= start_time) & (results["time_bin"] < end_time)
            ]

            if len(results) == 0:
                logger.warning(f"No results for {intersection} in requested period")
                return []

            # Convert to list of dictionaries, skipping rows with NaN values
            trend_data = []
            for _, row in results.iterrows():
                # Skip rows with NaN or infinite values
                if pd.isna(row["Safety_Score"]) or pd.isna(row["MCDM_Safety_Index"]):
                    logger.warning(
                        f"Skipping time bin {row['time_bin']} due to invalid score"
                    )
                    continue

                try:
                    trend_data.append(
                        {
                            "intersection": row["intersection"],
                            "time_bin": row["time_bin"],
                            "mcdm_index": float(row["MCDM_Safety_Index"]),
                            "vehicle_count": int(row["vehicle_count"]),
                            "vru_count": int(row["vru_count"]),
                            "avg_speed": float(row["avg_speed"]),
                            "speed_variance": float(row["speed_variance"]),
                            "incident_count": int(row["incident_count"]),
                            "near_miss_count": int(row.get("near_miss_count", 0)),
                            "saw_score": float(row["SAW"]),
                            "edas_score": float(row["EDAS"]),
                            "codas_score": float(row["CODAS"]),
                        }
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Skipping time bin {row['time_bin']} due to conversion error: {e}"
                    )
                    continue

            logger.info(
                f"Successfully calculated {len(trend_data)} time points for {intersection}"
            )
            return trend_data

        except Exception as e:
            logger.error(
                f"Error calculating safety score trend for {intersection}: {e}",
                exc_info=True,
            )
            return []

    def _calculate_trend_individually(
        self,
        matrix: pd.DataFrame,
        start_time: datetime,
        end_time: datetime,
        intersection: str,
    ) -> List[Dict]:
        """
        Calculate safety scores for each time bin individually, skipping bins that fail.

        This is a fallback method when batch calculation fails.
        """
        trend_data = []

        # Get unique time bins in the requested range
        time_bins = matrix[
            (matrix["time_bin"] >= start_time) & (matrix["time_bin"] < end_time)
        ]["time_bin"].unique()

        logger.info(
            f"Processing {len(time_bins)} time bins individually for {intersection}"
        )

        for time_bin in sorted(time_bins):
            try:
                # Get data for this specific time bin and 24 hours before for CRITIC
                lookback_start = time_bin - timedelta(days=1)
                bin_matrix = matrix[
                    (matrix["time_bin"] >= lookback_start)
                    & (matrix["time_bin"] <= time_bin)
                ].copy()

                if len(bin_matrix) < 2:  # Need at least 2 data points for CRITIC
                    logger.debug(f"Skipping {time_bin}: insufficient data")
                    continue

                # Calculate MCDM for this bin
                result = self._calculate_hybrid_mcdm(bin_matrix)

                # Get the row for the current time bin
                current_row = result[result["time_bin"] == time_bin]

                if len(current_row) == 0:
                    continue

                row = current_row.iloc[0]

                # Check for valid scores
                if pd.isna(row["Safety_Score"]) or pd.isna(row["MCDM_Safety_Index"]):
                    logger.debug(f"Skipping {time_bin}: invalid scores")
                    continue

                trend_data.append(
                    {
                        "intersection": row["intersection"],
                        "time_bin": row["time_bin"],
                        "safety_score": float(row["Safety_Score"]),
                        "mcdm_index": float(row["MCDM_Safety_Index"]),
                        "vehicle_count": int(row["vehicle_count"]),
                        "vru_count": int(row["vru_count"]),
                        "avg_speed": float(row["avg_speed"]),
                        "speed_variance": float(row["speed_variance"]),
                        "incident_count": int(row["incident_count"]),
                        "near_miss_count": int(row.get("near_miss_count", 0)),
                        "saw_score": float(row["SAW"]),
                        "edas_score": float(row["EDAS"]),
                        "codas_score": float(row["CODAS"]),
                    }
                )
            except Exception as e:
                logger.debug(f"Skipping {time_bin} due to error: {e}")
                continue

        logger.info(
            f"Successfully processed {len(trend_data)} out of {len(time_bins)} time bins"
        )
        return trend_data

    def get_available_intersections(self) -> List[str]:
        """
        Get list of available intersections from the intersection_details_view.

        Returns:
            List of unique intersection names
        """
        try:
            query = "SELECT DISTINCT intersection_name FROM public.intersection_details_view WHERE intersection_name IS NOT NULL;"
            results = self.client.execute_query(query)
            intersections = [
                row["intersection_name"] for row in results if row["intersection_name"]
            ]
            return sorted(intersections)
        except Exception as e:
            logger.error(f"Error getting available intersections: {e}", exc_info=True)
            return []
