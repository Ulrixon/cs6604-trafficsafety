"""
Correlation Analysis Service

Computes correlations between safety factors and outcomes to validate
that each component of RT-SI and MCDM indices corresponds to real safety mechanisms.

This includes:
- Pearson correlation (linear relationships)
- Spearman correlation (monotonic relationships)
- Partial correlations (independent contributions)
"""

import logging
from typing import Dict, List, Optional
import numpy as np
from scipy import stats
from scipy.stats import spearmanr, pearsonr
import pandas as pd

logger = logging.getLogger(__name__)


class CorrelationAnalysisService:
    """Analyze correlations between safety factors and outcomes."""

    def __init__(self):
        pass

    def compute_correlations(self, data: List[Dict]) -> Dict:
        """
        Compute correlations between variables and safety indices.

        Args:
            data: List of time point dictionaries containing all variables

        Returns:
            Dictionary with correlation analysis results
        """
        if not data or len(data) < 3:
            logger.warning("Insufficient data for correlation analysis")
            return {
                "error": "Insufficient data points (need at least 3)",
                "data_points": len(data) if data else 0,
            }

        try:
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(data)

            # Define variable groups
            traffic_vars = [
                "vehicle_count",
                "vru_count",
                "avg_speed",
                "speed_variance",
                "incident_count",
            ]

            rtsi_components = [
                "raw_crash_rate",
                "eb_crash_rate",
                "F_speed",
                "F_variance",
                "F_conflict",
                "uplift_factor",
                "vru_index",
                "vehicle_index",
            ]

            safety_indices = ["mcdm_index", "rt_si_score", "saw_score", "edas_score", "codas_score"]

            # Compute correlations for each variable group
            results = {
                "data_points": len(df),
                "traffic_to_safety": self._compute_variable_correlations(
                    df, traffic_vars, safety_indices
                ),
                "rtsi_components_to_rtsi": self._compute_variable_correlations(
                    df, rtsi_components, ["rt_si_score"]
                ),
                "traffic_to_incidents": self._compute_variable_correlations(
                    df, traffic_vars, ["incident_count"]
                ),
                "monotonic_trends": self._analyze_monotonic_trends(df),
                "partial_correlations": self._compute_partial_correlations(df),
                "summary": self._generate_summary(df),
            }

            return results

        except Exception as e:
            logger.error(f"Error computing correlations: {e}", exc_info=True)
            return {"error": str(e), "data_points": len(data) if data else 0}

    def _compute_variable_correlations(
        self, df: pd.DataFrame, predictors: List[str], targets: List[str]
    ) -> Dict:
        """
        Compute Pearson and Spearman correlations between predictor and target variables.

        Args:
            df: DataFrame with all variables
            predictors: List of predictor variable names
            targets: List of target variable names

        Returns:
            Dictionary with correlation results
        """
        results = {}

        for target in targets:
            if target not in df.columns:
                continue

            target_data = df[target].dropna()
            if len(target_data) < 3:
                continue

            results[target] = {}

            for predictor in predictors:
                if predictor not in df.columns or predictor == target:
                    continue

                # Align data (drop NaN in either variable)
                mask = df[predictor].notna() & df[target].notna()
                x = df.loc[mask, predictor].values
                y = df.loc[mask, target].values

                if len(x) < 3:
                    continue

                try:
                    # Pearson correlation (linear relationship)
                    pearson_result = pearsonr(x, y)
                    pearson_r = float(pearson_result[0])
                    pearson_p = float(pearson_result[1])

                    # Spearman correlation (monotonic relationship)
                    spearman_result = spearmanr(x, y)
                    spearman_r = float(spearman_result[0])
                    spearman_p = float(spearman_result[1])

                    results[target][predictor] = {
                        "pearson_r": float(pearson_r),
                        "pearson_p": float(pearson_p),
                        "pearson_significant": pearson_p < 0.05,
                        "spearman_r": float(spearman_r),
                        "spearman_p": float(spearman_p),
                        "spearman_significant": spearman_p < 0.05,
                        "n_samples": len(x),
                        "relationship": self._describe_relationship(
                            pearson_r, spearman_r, pearson_p, spearman_p
                        ),
                    }

                except Exception as e:
                    logger.warning(
                        f"Error computing correlation between {predictor} and {target}: {e}"
                    )
                    continue

        return results

    def _describe_relationship(
        self,
        pearson_r: float,
        spearman_r: float,
        pearson_p: float,
        spearman_p: float,
    ) -> str:
        """
        Describe the relationship based on correlation coefficients.

        Args:
            pearson_r: Pearson correlation coefficient
            spearman_r: Spearman correlation coefficient
            pearson_p: Pearson p-value
            spearman_p: Spearman p-value

        Returns:
            String description of the relationship
        """
        # Check significance
        pearson_sig = pearson_p < 0.05
        spearman_sig = spearman_p < 0.05

        if not pearson_sig and not spearman_sig:
            return "No significant relationship"

        # Determine strength
        abs_r = abs(pearson_r) if pearson_sig else abs(spearman_r)
        if abs_r < 0.3:
            strength = "Weak"
        elif abs_r < 0.7:
            strength = "Moderate"
        else:
            strength = "Strong"

        # Determine direction
        direction = "positive" if (pearson_r if pearson_sig else spearman_r) > 0 else "negative"

        # Determine type
        if pearson_sig and spearman_sig:
            if abs(pearson_r - spearman_r) < 0.1:
                relationship_type = "linear"
            else:
                relationship_type = "monotonic (non-linear)"
        elif pearson_sig:
            relationship_type = "linear"
        else:
            relationship_type = "monotonic"

        return f"{strength} {direction} {relationship_type}"

    def _analyze_monotonic_trends(self, df: pd.DataFrame) -> Dict:
        """
        Analyze monotonic trends to validate safety mechanisms.

        Returns trends like "higher speed variance → higher incident rate"
        """
        trends = {}

        # Key safety mechanism hypotheses to test
        hypotheses = [
            {
                "predictor": "speed_variance",
                "target": "incident_count",
                "expected": "positive",
                "mechanism": "Higher speed variance increases crash risk",
            },
            {
                "predictor": "avg_speed",
                "target": "incident_count",
                "expected": "positive",
                "mechanism": "Higher speed increases severity",
            },
            {
                "predictor": "vehicle_count",
                "target": "incident_count",
                "expected": "positive",
                "mechanism": "Higher volume increases exposure",
            },
            {
                "predictor": "vru_count",
                "target": "incident_count",
                "expected": "positive",
                "mechanism": "More VRUs increase conflict potential",
            },
            {
                "predictor": "F_speed",
                "target": "rt_si_score",
                "expected": "positive",
                "mechanism": "Speed reduction factor increases risk",
            },
            {
                "predictor": "F_variance",
                "target": "rt_si_score",
                "expected": "positive",
                "mechanism": "Speed variance factor increases risk",
            },
            {
                "predictor": "F_conflict",
                "target": "rt_si_score",
                "expected": "positive",
                "mechanism": "Conflict factor increases risk",
            },
            {
                "predictor": "eb_crash_rate",
                "target": "rt_si_score",
                "expected": "positive",
                "mechanism": "EB crash rate predicts RT-SI",
            },
        ]

        for hyp in hypotheses:
            predictor = hyp["predictor"]
            target = hyp["target"]

            if predictor not in df.columns or target not in df.columns:
                continue

            # Align data
            mask = df[predictor].notna() & df[target].notna()
            x = df.loc[mask, predictor].values
            y = df.loc[mask, target].values

            if len(x) < 3:
                continue

            try:
                # Spearman correlation for monotonic trend
                spearman_result = spearmanr(x, y)  # type: ignore
                spearman_r = float(spearman_result[0])  # type: ignore
                spearman_p = float(spearman_result[1])  # type: ignore

                # Check if trend matches expectation
                expected_direction = hyp["expected"]
                observed_direction = "positive" if spearman_r > 0 else "negative"
                matches_expectation = expected_direction == observed_direction
                is_significant = spearman_p < 0.05

                trends[f"{predictor}_to_{target}"] = {
                    "predictor": predictor,
                    "target": target,
                    "mechanism": hyp["mechanism"],
                    "expected_direction": expected_direction,
                    "observed_direction": observed_direction,
                    "spearman_r": float(spearman_r),
                    "p_value": float(spearman_p),
                    "significant": is_significant,
                    "matches_expectation": matches_expectation,
                    "validated": matches_expectation and is_significant,
                    "n_samples": len(x),
                }

            except Exception as e:
                logger.warning(f"Error analyzing trend {predictor} → {target}: {e}")
                continue

        return trends

    def _compute_partial_correlations(self, df: pd.DataFrame) -> Dict:
        """
        Compute partial correlations to show independent contributions.

        This controls for confounding variables to isolate the effect
        of each factor on safety outcomes.
        """
        results = {}

        # Key relationships to analyze with control variables
        analyses = [
            {
                "x": "speed_variance",
                "y": "incident_count",
                "control": ["vehicle_count"],
                "name": "speed_variance_to_incidents_controlling_volume",
            },
            {
                "x": "avg_speed",
                "y": "incident_count",
                "control": ["vehicle_count"],
                "name": "speed_to_incidents_controlling_volume",
            },
            {
                "x": "vru_count",
                "y": "incident_count",
                "control": ["vehicle_count"],
                "name": "vru_to_incidents_controlling_vehicle_volume",
            },
            {
                "x": "F_variance",
                "y": "rt_si_score",
                "control": ["F_speed"],
                "name": "variance_factor_independent_contribution",
            },
            {
                "x": "F_conflict",
                "y": "rt_si_score",
                "control": ["F_speed", "F_variance"],
                "name": "conflict_factor_independent_contribution",
            },
        ]

        for analysis in analyses:
            x_var = analysis["x"]
            y_var = analysis["y"]
            control_vars = analysis["control"]

            if (
                x_var not in df.columns
                or y_var not in df.columns
                or not all(c in df.columns for c in control_vars)
            ):
                continue

            try:
                partial_r = self._calculate_partial_correlation(
                    df, x_var, y_var, control_vars
                )

                if partial_r is not None:
                    results[analysis["name"]] = {
                        "x_variable": x_var,
                        "y_variable": y_var,
                        "control_variables": control_vars,
                        "partial_correlation": float(partial_r),
                        "interpretation": self._interpret_partial_correlation(
                            partial_r, x_var, y_var, control_vars
                        ),
                    }

            except Exception as e:
                logger.warning(f"Error computing partial correlation for {analysis['name']}: {e}")
                continue

        return results

    def _calculate_partial_correlation(
        self, df: pd.DataFrame, x: str, y: str, control: List[str]
    ) -> Optional[float]:
        """
        Calculate partial correlation between x and y, controlling for control variables.

        Uses residual method: correlate residuals of x~control with residuals of y~control
        """
        # Create combined mask for all variables
        mask = df[x].notna() & df[y].notna()
        for c in control:
            mask &= df[c].notna()

        data = df.loc[mask, [x, y] + control]

        if len(data) < 5:  # Need enough data points
            return None

        try:
            # Get residuals of x regressed on control variables
            x_resid = self._compute_residuals(data[x].values, data[control].values)  # type: ignore

            # Get residuals of y regressed on control variables
            y_resid = self._compute_residuals(data[y].values, data[control].values)  # type: ignore

            # Correlate the residuals
            partial_result = pearsonr(x_resid, y_resid)  # type: ignore
            partial_r = float(partial_result[0])  # type: ignore

            return partial_r

        except Exception as e:
            logger.warning(f"Error in partial correlation calculation: {e}")
            return None

    def _compute_residuals(self, y: np.ndarray, X: np.ndarray) -> np.ndarray:
        """
        Compute residuals from linear regression of y on X.

        Args:
            y: Dependent variable
            X: Independent variables (can be 1D or 2D)

        Returns:
            Residuals (y - y_predicted)
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        # Add intercept
        X_with_intercept = np.column_stack([np.ones(len(X)), X])

        # Compute coefficients using least squares
        coeffs, _, _, _ = np.linalg.lstsq(X_with_intercept, y, rcond=None)

        # Predict and compute residuals
        y_pred = X_with_intercept @ coeffs
        residuals = y - y_pred

        return residuals

    def _interpret_partial_correlation(
        self, r: float, x: str, y: str, control: List[str]
    ) -> str:
        """Generate interpretation of partial correlation result."""
        abs_r = abs(r)

        if abs_r < 0.1:
            strength = "negligible"
        elif abs_r < 0.3:
            strength = "weak"
        elif abs_r < 0.5:
            strength = "moderate"
        else:
            strength = "strong"

        direction = "positive" if r > 0 else "negative"

        control_str = ", ".join(control)

        return (
            f"{strength.capitalize()} {direction} independent relationship between {x} and {y} "
            f"after controlling for {control_str}"
        )

    def _generate_summary(self, df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics for the correlation analysis.

        Returns:
            Dictionary with summary information
        """
        summary = {
            "total_observations": len(df),
            "variables_analyzed": [],
            "significant_relationships": 0,
            "validated_mechanisms": 0,
        }

        # Count variables with sufficient data
        for col in df.columns:
            if df[col].notna().sum() >= 3:
                summary["variables_analyzed"].append(col)

        return summary
