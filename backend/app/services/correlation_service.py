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

            safety_indices = [
                "mcdm_index",
                "rt_si_score",
                "saw_score",
                "edas_score",
                "codas_score",
            ]

            # Get all available variables
            all_vars = [
                col for col in df.columns if col not in ["time_bin", "intersection"]
            ]

            # Compute all pairwise correlations
            variable_correlations = {}

            for i, var1 in enumerate(all_vars):
                for var2 in all_vars[i + 1 :]:
                    # Align data (drop NaN in either variable)
                    mask = df[var1].notna() & df[var2].notna()
                    x = df.loc[mask, var1].values
                    y = df.loc[mask, var2].values

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

                        variable_correlations[f"{var1}_vs_{var2}"] = {
                            "variable_1": var1,
                            "variable_2": var2,
                            "pearson": {
                                "correlation": float(pearson_r),
                                "p_value": float(pearson_p),
                                "significant": pearson_p < 0.05,
                            },
                            "spearman": {
                                "correlation": float(spearman_r),
                                "p_value": float(spearman_p),
                                "significant": spearman_p < 0.05,
                            },
                            "n_samples": len(x),
                            "description": self._describe_relationship(
                                pearson_r, spearman_r, pearson_p, spearman_p
                            ),
                        }

                    except Exception as e:
                        logger.warning(
                            f"Error computing correlation between {var1} and {var2}: {e}"
                        )
                        continue

            # Compute summary statistics
            summary = {
                "total_variables": len(all_vars),
                "total_correlations": len(variable_correlations),
                "significant_pearson": sum(
                    1
                    for v in variable_correlations.values()
                    if v["pearson"]["significant"]
                ),
                "significant_spearman": sum(
                    1
                    for v in variable_correlations.values()
                    if v["spearman"]["significant"]
                ),
                "strong_correlations": sum(
                    1
                    for v in variable_correlations.values()
                    if abs(v["pearson"]["correlation"]) > 0.7
                    or abs(v["spearman"]["correlation"]) > 0.7
                ),
                "moderate_correlations": sum(
                    1
                    for v in variable_correlations.values()
                    if (0.3 < abs(v["pearson"]["correlation"]) <= 0.7)
                    or (0.3 < abs(v["spearman"]["correlation"]) <= 0.7)
                ),
            }

            results = {
                "data_points": len(df),
                "variable_correlations": variable_correlations,
                "summary": summary,
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
        direction = (
            "positive" if (pearson_r if pearson_sig else spearman_r) > 0 else "negative"
        )

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
                logger.warning(
                    f"Error computing partial correlation for {analysis['name']}: {e}"
                )
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
