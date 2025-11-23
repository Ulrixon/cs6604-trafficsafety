"""
Sensitivity Analysis Service

Performs sensitivity analysis on RT-SI and MCDM parameters to validate
robustness of the safety index methodology.

Parameters analyzed:
- β₁, β₂, β₃: Uplift weights (BETA1, BETA2, BETA3)
- k₁...k₅: Scaling constants (K1_SPEED, K2_VAR, K3_CONF, K4_VRU_RATIO, K5_VOL_CAPACITY)
- λ: Empirical Bayes shrinkage (LAMBDA)
- ω: VRU vs Vehicle blend (OMEGA_VRU, OMEGA_VEH)
- α: Real-time vs MCDM blend (external to this service)
"""

import logging
import random
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np
from scipy.stats import spearmanr

from app.services.rt_si_service import RTSIService
from app.services.mcdm_service import MCDMSafetyIndexService
from app.services.db_client import VTTIPostgresClient

logger = logging.getLogger(__name__)


class SensitivityAnalysisService:
    """Perform sensitivity analysis on safety index parameters."""

    def __init__(self, db_client: VTTIPostgresClient):
        self.db_client = db_client
        self.base_rt_si_service = RTSIService(db_client)
        self.base_mcdm_service = MCDMSafetyIndexService(db_client)

    def generate_parameter_perturbations(
        self, perturbation_pct: float = 0.25, n_samples: int = 100
    ) -> List[Dict]:
        """
        Generate random parameter perturbations.

        Args:
            perturbation_pct: Percentage to perturb (0.25 = ±25%)
            n_samples: Number of parameter sets to generate

        Returns:
            List of parameter dictionaries
        """
        base_params = {
            "LAMBDA": self.base_rt_si_service.LAMBDA,
            "BETA1": self.base_rt_si_service.BETA1,
            "BETA2": self.base_rt_si_service.BETA2,
            "BETA3": self.base_rt_si_service.BETA3,
            "K1_SPEED": self.base_rt_si_service.K1_SPEED,
            "K2_VAR": self.base_rt_si_service.K2_VAR,
            "K3_CONF": self.base_rt_si_service.K3_CONF,
            "K4_VRU_RATIO": self.base_rt_si_service.K4_VRU_RATIO,
            "K5_VOL_CAPACITY": self.base_rt_si_service.K5_VOL_CAPACITY,
            "OMEGA_VRU": self.base_rt_si_service.OMEGA_VRU,
            "OMEGA_VEH": self.base_rt_si_service.OMEGA_VEH,
        }

        perturbations = []

        # Include baseline
        perturbations.append({"params": base_params.copy(), "label": "baseline"})

        # Generate random perturbations
        for i in range(n_samples):
            perturbed = {}
            for param, base_value in base_params.items():
                # Random perturbation between -perturbation_pct and +perturbation_pct
                perturbation = random.uniform(-perturbation_pct, perturbation_pct)
                perturbed[param] = base_value * (1 + perturbation)

            # Normalize OMEGA values to sum to 1.0
            omega_sum = perturbed["OMEGA_VRU"] + perturbed["OMEGA_VEH"]
            perturbed["OMEGA_VRU"] /= omega_sum
            perturbed["OMEGA_VEH"] /= omega_sum

            # Normalize BETA values to sum to 1.0
            beta_sum = perturbed["BETA1"] + perturbed["BETA2"] + perturbed["BETA3"]
            perturbed["BETA1"] /= beta_sum
            perturbed["BETA2"] /= beta_sum
            perturbed["BETA3"] /= beta_sum

            perturbations.append({"params": perturbed, "label": f"perturb_{i+1}"})

        return perturbations

    def compute_rt_si_with_params(
        self,
        intersection_id: int,
        timestamp: datetime,
        params: Dict,
        bin_minutes: int = 15,
        realtime_intersection: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Compute RT-SI with custom parameters.

        Args:
            intersection_id: Crash intersection ID
            timestamp: Time to calculate RT-SI for
            params: Parameter dictionary
            bin_minutes: Time bin size
            realtime_intersection: BSM intersection name

        Returns:
            RT-SI result dict or None
        """
        # Create temporary service with perturbed parameters
        temp_service = RTSIService(self.db_client)

        # Override parameters
        temp_service.LAMBDA = params["LAMBDA"]
        temp_service.BETA1 = params["BETA1"]
        temp_service.BETA2 = params["BETA2"]
        temp_service.BETA3 = params["BETA3"]
        temp_service.K1_SPEED = params["K1_SPEED"]
        temp_service.K2_VAR = params["K2_VAR"]
        temp_service.K3_CONF = params["K3_CONF"]
        temp_service.K4_VRU_RATIO = params["K4_VRU_RATIO"]
        temp_service.K5_VOL_CAPACITY = params["K5_VOL_CAPACITY"]
        temp_service.OMEGA_VRU = params["OMEGA_VRU"]
        temp_service.OMEGA_VEH = params["OMEGA_VEH"]

        # Calculate RT-SI
        return temp_service.calculate_rt_si(
            intersection_id,
            timestamp,
            bin_minutes=bin_minutes,
            realtime_intersection=realtime_intersection,
        )

    def analyze_sensitivity(
        self,
        intersection: str,
        start_time: datetime,
        end_time: datetime,
        bin_minutes: int = 15,
        perturbation_pct: float = 0.25,
        n_samples: int = 100,
    ) -> Dict:
        """
        Perform sensitivity analysis across a time range.

        Args:
            intersection: BSM intersection name
            start_time: Start of time range
            end_time: End of time range
            bin_minutes: Time bin size
            perturbation_pct: Percentage to perturb parameters
            n_samples: Number of parameter sets to test

        Returns:
            Dictionary with sensitivity analysis results
        """
        from app.api.intersection import find_crash_intersection_for_bsm

        # Find crash intersection ID
        crash_intersection_id = find_crash_intersection_for_bsm(
            intersection, self.db_client
        )

        if not crash_intersection_id:
            return {
                "error": f"No crash intersection found for '{intersection}'",
                "intersection": intersection,
            }

        # Generate parameter perturbations
        perturbations = self.generate_parameter_perturbations(
            perturbation_pct, n_samples
        )

        # Calculate baseline RT-SI trend
        logger.info(f"Computing baseline RT-SI trend for {intersection}")
        baseline_results = self.base_rt_si_service.calculate_rt_si_trend(
            crash_intersection_id,
            start_time,
            end_time,
            bin_minutes=bin_minutes,
            realtime_intersection=intersection,
        )

        if not baseline_results:
            return {
                "error": "No baseline data available",
                "intersection": intersection,
            }

        baseline_scores = [r["RT_SI"] for r in baseline_results]
        timestamps = [r["timestamp"] for r in baseline_results]

        # Store all perturbed results
        all_perturbed_scores = []
        parameter_details = []

        logger.info(f"Running {n_samples} sensitivity iterations")

        # Compute RT-SI for each parameter set
        for perturb in perturbations[1:]:  # Skip baseline (already computed)
            params = perturb["params"]
            label = perturb["label"]

            perturbed_scores = []

            for i, ts_str in enumerate(timestamps):
                ts = datetime.fromisoformat(ts_str)
                result = self.compute_rt_si_with_params(
                    crash_intersection_id,
                    ts,
                    params,
                    bin_minutes=bin_minutes,
                    realtime_intersection=intersection,
                )

                if result:
                    perturbed_scores.append(result["RT_SI"])
                else:
                    perturbed_scores.append(baseline_scores[i])  # Fallback to baseline

            all_perturbed_scores.append(perturbed_scores)

            # Store parameter set for reference
            parameter_details.append(
                {"label": label, "params": params, "scores": perturbed_scores}
            )

        # Compute stability metrics
        stability_metrics = self._compute_stability_metrics(
            baseline_scores, all_perturbed_scores, timestamps
        )

        # Compute parameter importance
        parameter_importance = self._compute_parameter_importance(
            parameter_details, baseline_scores
        )

        return {
            "intersection": intersection,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "bin_minutes": bin_minutes,
            },
            "perturbation_settings": {
                "perturbation_pct": perturbation_pct,
                "n_samples": n_samples,
            },
            "baseline": {
                "timestamps": timestamps,
                "rt_si_scores": baseline_scores,
            },
            "stability_metrics": stability_metrics,
            "parameter_importance": parameter_importance,
            "perturbed_samples": parameter_details[:10],  # Return first 10 for inspection
        }

    def _compute_stability_metrics(
        self, baseline: List[float], perturbed_list: List[List[float]], timestamps: List[str]
    ) -> Dict:
        """
        Compute stability metrics comparing baseline to perturbed results.

        Returns:
            - spearman_correlations: rank correlation for each perturbation
            - mean_spearman: average correlation
            - score_changes: statistics on score differences
            - tier_changes: number of risk tier changes
        """
        spearman_correlations = []
        score_differences = []

        for perturbed in perturbed_list:
            # Spearman rank correlation
            if len(baseline) >= 3:
                corr, _ = spearmanr(baseline, perturbed)
                spearman_correlations.append(float(corr) if not np.isnan(corr) else 0.0)

            # Score differences
            diffs = [abs(b - p) for b, p in zip(baseline, perturbed)]
            score_differences.extend(diffs)

        # Risk tier classification
        def classify_tier(score):
            if score >= 75:
                return "High Safety"
            elif score >= 50:
                return "Medium Safety"
            elif score >= 25:
                return "Low Safety"
            else:
                return "Critical"

        # Count tier changes
        tier_changes = []
        for perturbed in perturbed_list:
            changes = sum(
                1
                for b, p in zip(baseline, perturbed)
                if classify_tier(b) != classify_tier(p)
            )
            tier_changes.append(changes)

        return {
            "spearman_correlations": {
                "values": spearman_correlations,
                "mean": float(np.mean(spearman_correlations)) if spearman_correlations else 0.0,
                "std": float(np.std(spearman_correlations)) if spearman_correlations else 0.0,
                "min": float(np.min(spearman_correlations)) if spearman_correlations else 0.0,
                "max": float(np.max(spearman_correlations)) if spearman_correlations else 0.0,
            },
            "score_changes": {
                "mean": float(np.mean(score_differences)) if score_differences else 0.0,
                "std": float(np.std(score_differences)) if score_differences else 0.0,
                "max": float(np.max(score_differences)) if score_differences else 0.0,
                "percentile_95": float(np.percentile(score_differences, 95)) if score_differences else 0.0,
            },
            "tier_changes": {
                "values": tier_changes,
                "mean": float(np.mean(tier_changes)) if tier_changes else 0.0,
                "max": int(np.max(tier_changes)) if tier_changes else 0,
                "percentage_no_change": (
                    sum(1 for x in tier_changes if x == 0) / len(tier_changes) * 100
                    if tier_changes
                    else 0.0
                ),
            },
            "total_perturbations": len(perturbed_list),
            "total_time_points": len(baseline),
        }

    def _compute_parameter_importance(
        self, parameter_details: List[Dict], baseline: List[float]
    ) -> Dict:
        """
        Compute which parameters have the most impact on results.

        Uses correlation between parameter deviation and score deviation.
        """
        if not parameter_details:
            return {}

        param_names = list(parameter_details[0]["params"].keys())
        baseline_params = self.base_rt_si_service

        # Get baseline parameter values
        baseline_param_values = {
            "LAMBDA": baseline_params.LAMBDA,
            "BETA1": baseline_params.BETA1,
            "BETA2": baseline_params.BETA2,
            "BETA3": baseline_params.BETA3,
            "K1_SPEED": baseline_params.K1_SPEED,
            "K2_VAR": baseline_params.K2_VAR,
            "K3_CONF": baseline_params.K3_CONF,
            "K4_VRU_RATIO": baseline_params.K4_VRU_RATIO,
            "K5_VOL_CAPACITY": baseline_params.K5_VOL_CAPACITY,
            "OMEGA_VRU": baseline_params.OMEGA_VRU,
            "OMEGA_VEH": baseline_params.OMEGA_VEH,
        }

        importance = {}

        for param in param_names:
            param_deviations = []
            score_deviations = []

            for detail in parameter_details:
                # Parameter deviation (normalized)
                param_value = detail["params"][param]
                baseline_value = baseline_param_values[param]
                param_dev = abs(param_value - baseline_value) / (baseline_value + 1e-10)

                # Score deviation (mean absolute difference)
                scores = detail["scores"]
                score_dev = np.mean([abs(s - b) for s, b in zip(scores, baseline)])

                param_deviations.append(param_dev)
                score_deviations.append(score_dev)

            # Correlation between parameter deviation and score deviation
            if len(param_deviations) >= 3:
                corr, _ = spearmanr(param_deviations, score_deviations)
                importance[param] = {
                    "correlation": float(corr) if not np.isnan(corr) else 0.0,
                    "interpretation": (
                        "High Impact" if abs(corr) > 0.5 else
                        "Moderate Impact" if abs(corr) > 0.3 else
                        "Low Impact"
                    )
                }
            else:
                importance[param] = {"correlation": 0.0, "interpretation": "Unknown"}

        # Sort by absolute correlation
        sorted_importance = dict(
            sorted(
                importance.items(),
                key=lambda x: abs(x[1]["correlation"]),
                reverse=True,
            )
        )

        return sorted_importance
