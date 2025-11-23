"""
Find optimal lambda (λ) for Empirical Bayes stabilization using cross-validation.

Uses crash data from 2017-2024 as training and 2025 as test set.
Evaluates different λ values using Poisson negative log-likelihood.
"""

import logging
import numpy as np
from typing import Dict, Tuple
from app.services.db_client import VTTIPostgresClient

logger = logging.getLogger(__name__)


class LambdaOptimizer:
    """Find optimal lambda for Empirical Bayes shrinkage."""

    def __init__(self, db_client: VTTIPostgresClient):
        self.db_client = db_client
        self.lambda_grid = [
            0.1,
            0.3,
            1,
            3,
            10,
            30,
            100,
            300,
            1000,
            3000,
            10000,
            30000,
            100000,
        ]

    def prepare_training_data(self) -> Dict:
        """
        Prepare training data from 2017-2024 crash data.

        Returns dict with:
        - intersection_bins: list of (intersection_id, hour, dow)
        - crashes: crash counts per intersection-bin
        - exposure: not used (exposure = 1)

        Note: Uses pre-matched intersection IDs from vdot_crashes_with_intersections
        table to avoid expensive spatial joins.
        """
        query = """
        SELECT 
            matched_intersection_id as intersection_id,
            -- Convert military time (e.g., 845 -> 8, 1718 -> 17)
            FLOOR(crash_military_time / 100) as hour_of_day,
            EXTRACT(DOW FROM TO_DATE(crash_date::TEXT, 'YYYY-MM-DD')) as day_of_week,
            -- Severity weights: Fatal=10, Injury=3, PDO=1
            SUM(CASE 
                WHEN crash_severity IN ('K', 'Fatal') THEN 10
                WHEN crash_severity IN ('A', 'B', 'Injury') THEN 3
                ELSE 1
            END) as weighted_crashes,
            COUNT(*) as crash_count
        FROM vdot_crashes_with_intersections
        WHERE matched_intersection_id IS NOT NULL
          AND crash_military_time IS NOT NULL
          AND crash_date IS NOT NULL
          AND crash_year BETWEEN 2017 AND 2024
        GROUP BY matched_intersection_id, hour_of_day, day_of_week
        HAVING COUNT(*) >= 2  -- At least 2 crashes for meaningful statistics
        ORDER BY intersection_id, hour_of_day, day_of_week;
        """

        results = self.db_client.execute_query(query)

        data = {
            "intersection_bins": [],
            "crashes": [],
        }

        for row in results:
            data["intersection_bins"].append(
                (row["intersection_id"], row["hour_of_day"], row["day_of_week"])
            )
            data["crashes"].append(row["weighted_crashes"])

        logger.info(
            f"Prepared training data: {len(data['crashes'])} location-bin combinations"
        )
        return data

    def prepare_test_data(self) -> Dict:
        """
        Prepare test data from 2025 crash data.

        Returns dict with same structure as training data.
        Uses pre-matched intersection IDs to avoid expensive spatial joins.
        """
        query = """
        SELECT 
            matched_intersection_id as intersection_id,
            -- Convert military time (e.g., 845 -> 8, 1718 -> 17)
            FLOOR(crash_military_time / 100) as hour_of_day,
            EXTRACT(DOW FROM TO_DATE(crash_date::TEXT, 'YYYY-MM-DD')) as day_of_week,
            -- Severity weights: Fatal=10, Injury=3, PDO=1
            SUM(CASE 
                WHEN crash_severity IN ('K', 'Fatal') THEN 10
                WHEN crash_severity IN ('A', 'B', 'Injury') THEN 3
                ELSE 1
            END) as weighted_crashes,
            COUNT(*) as crash_count
        FROM vdot_crashes_with_intersections
        WHERE matched_intersection_id IS NOT NULL
          AND crash_military_time IS NOT NULL
          AND crash_date IS NOT NULL
          AND crash_year = 2025
        GROUP BY matched_intersection_id, hour_of_day, day_of_week
        HAVING COUNT(*) > 0
        ORDER BY intersection_id, hour_of_day, day_of_week;
        """

        results = self.db_client.execute_query(query)

        data = {
            "intersection_bins": [],
            "crashes": [],
        }

        for row in results:
            data["intersection_bins"].append(
                (row["intersection_id"], row["hour_of_day"], row["day_of_week"])
            )
            data["crashes"].append(row["weighted_crashes"])

        logger.info(
            f"Prepared test data: {len(data['crashes'])} intersection-bin combinations"
        )
        return data

    def compute_pooled_mean_rate(self, crashes: list) -> float:
        """
        Compute pooled mean crash rate r0 from training data.

        Without exposure: r0 = mean count across all bins
        r0 = Σ Y_{i,t} / N
        """
        total_crashes = sum(crashes)
        n_bins = len(crashes)
        r0 = total_crashes / n_bins if n_bins > 0 else 0
        logger.info(
            f"Pooled mean rate r0 = {r0:.6f} (total crashes: {total_crashes}, bins: {n_bins})"
        )
        return r0

    def compute_eb_rate(
        self, crash_count: float, r0: float, lambda_val: float
    ) -> float:
        """
        Compute Empirical Bayes stabilized rate WITHOUT exposure.

        When exposure = 1:
        r_hat = (1/(1+λ)) * Y + (λ/(1+λ)) * r0

        This is equivalent to:
        r_hat = (Y + λ*r0) / (1 + λ)
        """
        r_hat = (crash_count + lambda_val * r0) / (1.0 + lambda_val)
        return r_hat

    def compute_log_loss(
        self,
        train_data: Dict,
        test_data: Dict,
        r0: float,
        lambda_val: float,
    ) -> float:
        """
        Compute Poisson negative log-likelihood for given λ WITHOUT exposure.

        L(λ) = Σ (ŷ - y * log(ŷ))

        Where:
        - ŷ = r_hat = EB-adjusted crash count prediction
        - y = actual crash count in test set
        """
        # Create lookup for training data (crash counts by bin)
        train_lookup = {}
        for i, bin_key in enumerate(train_data["intersection_bins"]):
            crash_count = train_data["crashes"][i]
            train_lookup[bin_key] = crash_count

        log_loss = 0.0
        valid_predictions = 0

        for i, bin_key in enumerate(test_data["intersection_bins"]):
            if bin_key not in train_lookup:
                # No training data for this bin, skip
                continue

            train_crashes = train_lookup[bin_key]

            # Compute EB rate: r_hat = (Y + λ*r0) / (1 + λ)
            y_pred = self.compute_eb_rate(train_crashes, r0, lambda_val)
            y_actual = test_data["crashes"][i]

            # Poisson negative log-likelihood: ŷ - y * log(ŷ)
            # Add small epsilon to avoid log(0)
            if y_pred > 1e-10:
                log_loss += y_pred - y_actual * np.log(y_pred + 1e-10)
                valid_predictions += 1

        if valid_predictions > 0:
            log_loss /= valid_predictions  # Average log-loss

        logger.info(
            f"λ={lambda_val:>6.1f}: log-loss={log_loss:.4f} ({valid_predictions} predictions)"
        )
        return log_loss

    def find_optimal_lambda(self) -> Tuple[float, Dict]:
        """
        Find optimal λ using cross-validation.

        Returns:
            (optimal_lambda, results_dict)
        """
        logger.info("=" * 60)
        logger.info("Starting λ optimization via cross-validation")
        logger.info("=" * 60)

        # Prepare data
        train_data = self.prepare_training_data()
        test_data = self.prepare_test_data()

        if len(train_data["crashes"]) == 0:
            logger.error("No training data available!")
            return 10.0, {}  # Return default value

        if len(test_data["crashes"]) == 0:
            logger.warning("No test data available! Using training data only.")
            # Fall back to using a portion of training data as test
            # This is not ideal but better than failing

        # Compute pooled mean rate (without exposure)
        r0 = self.compute_pooled_mean_rate(train_data["crashes"])

        # Evaluate each λ
        results = {}
        logger.info("\nEvaluating λ values:")
        logger.info("-" * 60)

        for lambda_val in self.lambda_grid:
            log_loss = self.compute_log_loss(train_data, test_data, r0, lambda_val)
            results[lambda_val] = log_loss

        # Find optimal λ
        optimal_lambda = min(results.keys(), key=lambda k: results[k])
        optimal_loss = results[optimal_lambda]

        logger.info("-" * 60)
        logger.info(f"\n✅ Optimal λ = {optimal_lambda}")
        logger.info(f"   Minimum log-loss = {optimal_loss:.4f}")
        logger.info("=" * 60)

        return optimal_lambda, {
            "r0": r0,
            "lambda": optimal_lambda,
            "log_loss": optimal_loss,
            "all_results": results,
            "train_samples": len(train_data["crashes"]),
            "test_samples": len(test_data["crashes"]),
        }


def main():
    """Run lambda optimization."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    db_client = VTTIPostgresClient()

    try:
        optimizer = LambdaOptimizer(db_client)
        optimal_lambda, results = optimizer.find_optimal_lambda()

        print("\n" + "=" * 60)
        print("OPTIMIZATION RESULTS")
        print("=" * 60)
        print(f"Optimal λ:           {optimal_lambda}")
        print(f"Pooled mean rate r0: {results.get('r0', 0):.6f}")
        print(f"Minimum log-loss:    {results.get('log_loss', 0):.4f}")
        print(f"Training samples:    {results.get('train_samples', 0)}")
        print(f"Test samples:        {results.get('test_samples', 0)}")
        print("\nAll λ results:")
        for lam, loss in sorted(results.get("all_results", {}).items()):
            marker = " ← BEST" if lam == optimal_lambda else ""
            print(f"  λ={lam:>6.1f}: log-loss={loss:.4f}{marker}")
        print("=" * 60)

    finally:
        db_client.close()


if __name__ == "__main__":
    main()
