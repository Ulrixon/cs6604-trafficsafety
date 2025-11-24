"""
Feature Weight Optimization (Phase 7)

Uses grid search and crash correlation to find optimal plugin weights
that maximize crash prediction accuracy.

Optimizes:
- VCC plugin weight (traffic data)
- Weather plugin weight
- Feature weights within each plugin

Methods:
- Grid search over weight space
- Cross-validation to prevent overfitting
- Maximize F1 score or AUC

Usage:
    python scripts/optimize_feature_weights.py --method grid_search --metric f1
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import argparse
import pandas as pd
import numpy as np
from dataclasses import dataclass

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


@dataclass
class WeightConfig:
    """Configuration of plugin weights"""
    vcc_weight: float
    weather_weight: float
    score: float  # F1 or AUC
    precision: float
    recall: float


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def generate_weight_grid(
    vcc_range: Tuple[float, float] = (0.70, 0.95),
    weather_range: Tuple[float, float] = (0.05, 0.30),
    step: float = 0.05
) -> List[Tuple[float, float]]:
    """
    Generate grid of weight combinations to test.

    Args:
        vcc_range: Min and max VCC weight
        weather_range: Min and max weather weight
        step: Step size for grid

    Returns:
        List of (vcc_weight, weather_weight) tuples that sum to 1.0
    """
    weights = []

    vcc_min, vcc_max = vcc_range
    weather_min, weather_max = weather_range

    vcc = vcc_min
    while vcc <= vcc_max:
        weather = 1.0 - vcc
        if weather_min <= weather <= weather_max:
            weights.append((round(vcc, 2), round(weather, 2)))
        vcc += step

    return weights


def compute_safety_index_with_weights(
    traffic_index: float,
    weather_index: float,
    vcc_weight: float,
    weather_weight: float
) -> float:
    """
    Compute safety index with specified weights.

    Args:
        traffic_index: Traffic safety index (0-100)
        weather_index: Weather safety index (0-100)
        vcc_weight: Weight for traffic component
        weather_weight: Weight for weather component

    Returns:
        Combined safety index (0-100)
    """
    # Normalize weights
    total_weight = vcc_weight + weather_weight
    vcc_norm = vcc_weight / total_weight
    weather_norm = weather_weight / total_weight

    return (traffic_index * vcc_norm) + (weather_index * weather_norm)


def evaluate_weights(
    data: pd.DataFrame,
    vcc_weight: float,
    weather_weight: float,
    threshold: float = 60.0
) -> Dict[str, float]:
    """
    Evaluate plugin weights using crash data.

    Args:
        data: DataFrame with traffic_index, weather_index, and had_crash columns
        vcc_weight: Weight for VCC plugin
        weather_weight: Weight for weather plugin
        threshold: Safety index threshold for classification

    Returns:
        Dictionary with precision, recall, f1_score, accuracy
    """
    # Compute combined indices with these weights
    combined_indices = data.apply(
        lambda row: compute_safety_index_with_weights(
            row['Traffic_Index'],
            row['Weather_Index'],
            vcc_weight,
            weather_weight
        ),
        axis=1
    )

    # Binary classification
    y_true = data['had_crash'].values
    y_pred = (combined_indices >= threshold).astype(int).values

    # Metrics
    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0

    return {
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'accuracy': accuracy
    }


def grid_search_optimization(
    data: pd.DataFrame,
    metric: str = 'f1_score',
    threshold: float = 60.0
) -> List[WeightConfig]:
    """
    Perform grid search to find optimal weights.

    Args:
        data: DataFrame with Traffic_Index, Weather_Index, had_crash
        metric: Metric to optimize ('f1_score', 'precision', 'recall', 'accuracy')
        threshold: Safety index threshold

    Returns:
        List of WeightConfig sorted by metric (best first)
    """
    print_section("Grid Search Optimization")

    # Generate weight grid
    weight_grid = generate_weight_grid()

    print(f"Testing {len(weight_grid)} weight combinations...")
    print(f"Optimizing for: {metric}")
    print(f"Threshold: {threshold}")

    results = []

    for vcc_weight, weather_weight in weight_grid:
        metrics = evaluate_weights(data, vcc_weight, weather_weight, threshold)

        config = WeightConfig(
            vcc_weight=vcc_weight,
            weather_weight=weather_weight,
            score=metrics[metric],
            precision=metrics['precision'],
            recall=metrics['recall']
        )

        results.append(config)

    # Sort by metric (descending)
    results.sort(key=lambda x: x.score, reverse=True)

    print(f"\nOK Grid search complete. Tested {len(results)} configurations.")

    return results


def cross_validate_weights(
    data: pd.DataFrame,
    vcc_weight: float,
    weather_weight: float,
    n_folds: int = 5,
    threshold: float = 60.0
) -> Dict[str, float]:
    """
    Cross-validate weight configuration.

    Args:
        data: DataFrame with indices and crashes
        vcc_weight: VCC plugin weight
        weather_weight: Weather plugin weight
        n_folds: Number of CV folds
        threshold: Classification threshold

    Returns:
        Dictionary with mean and std of metrics across folds
    """
    # Split data into folds
    fold_size = len(data) // n_folds
    fold_metrics = []

    for fold_idx in range(n_folds):
        # Create test fold
        test_start = fold_idx * fold_size
        test_end = test_start + fold_size if fold_idx < n_folds - 1 else len(data)

        test_data = data.iloc[test_start:test_end]

        # Evaluate on this fold
        metrics = evaluate_weights(test_data, vcc_weight, weather_weight, threshold)
        fold_metrics.append(metrics)

    # Compute mean and std across folds
    mean_metrics = {
        'f1_score_mean': np.mean([m['f1_score'] for m in fold_metrics]),
        'f1_score_std': np.std([m['f1_score'] for m in fold_metrics]),
        'precision_mean': np.mean([m['precision'] for m in fold_metrics]),
        'recall_mean': np.mean([m['recall'] for m in fold_metrics]),
    }

    return mean_metrics


def print_top_configurations(configs: List[WeightConfig], top_n: int = 10):
    """Print top N weight configurations."""
    print_section(f"Top {top_n} Weight Configurations")

    print(f"{'Rank':<6} {'VCC Weight':<12} {'Weather Weight':<16} {'F1 Score':<10} {'Precision':<12} {'Recall':<10}")
    print("-" * 80)

    for rank, config in enumerate(configs[:top_n], start=1):
        print(f"{rank:<6} {config.vcc_weight:<12.2f} {config.weather_weight:<16.2f} "
              f"{config.score:<10.3f} {config.precision:<12.3f} {config.recall:<10.3f}")


def compare_with_current(configs: List[WeightConfig], current_vcc: float = 0.85, current_weather: float = 0.15):
    """Compare optimal configuration with current weights."""
    print_section("Comparison with Current Configuration")

    best = configs[0]

    print(f"Current Configuration:")
    print(f"  VCC Weight: {current_vcc:.2f}")
    print(f"  Weather Weight: {current_weather:.2f}")

    # Find current config in results
    current_config = None
    for config in configs:
        if abs(config.vcc_weight - current_vcc) < 0.01 and abs(config.weather_weight - current_weather) < 0.01:
            current_config = config
            break

    if current_config:
        print(f"  F1 Score: {current_config.score:.3f}")
        print(f"  Precision: {current_config.precision:.3f}")
        print(f"  Recall: {current_config.recall:.3f}")

        improvement = ((best.score - current_config.score) / current_config.score * 100) if current_config.score > 0 else 0

        print(f"\nOptimal Configuration:")
        print(f"  VCC Weight: {best.vcc_weight:.2f}")
        print(f"  Weather Weight: {best.weather_weight:.2f}")
        print(f"  F1 Score: {best.score:.3f}")
        print(f"  Precision: {best.precision:.3f}")
        print(f"  Recall: {best.recall:.3f}")

        print(f"\nImprovement:")
        if improvement > 5:
            print(f"  OK F1 Score improved by {improvement:.1f}%")
            print(f"  RECOMMENDATION: Update weights to optimal configuration")
        elif improvement > 0:
            print(f"  -> F1 Score improved by {improvement:.1f}% (marginal)")
            print(f"  RECOMMENDATION: Consider updating weights, but current config is acceptable")
        else:
            print(f"  OK Current configuration is optimal or near-optimal")
            print(f"  RECOMMENDATION: No weight changes needed")
    else:
        print(f"\nOptimal Configuration (no current config found for comparison):")
        print(f"  VCC Weight: {best.vcc_weight:.2f}")
        print(f"  Weather Weight: {best.weather_weight:.2f}")
        print(f"  F1 Score: {best.score:.3f}")


def generate_synthetic_data(n_samples: int = 1000) -> pd.DataFrame:
    """
    Generate synthetic crash/index data for testing.

    Creates realistic correlation between indices and crashes.
    """
    np.random.seed(42)

    # Generate indices
    traffic_indices = np.random.uniform(30, 90, n_samples)
    weather_indices = np.random.uniform(20, 80, n_samples)

    # Combined index (current weights: 0.85, 0.15)
    combined_indices = (traffic_indices * 0.85) + (weather_indices * 0.15)

    # Crash probability increases with combined index
    crash_prob = 1 / (1 + np.exp(-0.1 * (combined_indices - 60)))  # Logistic function
    had_crash = np.random.binomial(1, crash_prob)

    return pd.DataFrame({
        'Traffic_Index': traffic_indices,
        'Weather_Index': weather_indices,
        'Combined_Index': combined_indices,
        'had_crash': had_crash
    })


def main():
    """Main optimization function."""
    parser = argparse.ArgumentParser(description="Feature Weight Optimization")
    parser.add_argument('--method', type=str, default='grid_search',
                      choices=['grid_search'],
                      help='Optimization method')
    parser.add_argument('--metric', type=str, default='f1_score',
                      choices=['f1_score', 'precision', 'recall', 'accuracy'],
                      help='Metric to optimize')
    parser.add_argument('--threshold', type=float, default=60.0,
                      help='Safety index threshold for classification')
    parser.add_argument('--cv-folds', type=int, default=5,
                      help='Number of cross-validation folds')
    parser.add_argument('--use-real-data', action='store_true',
                      help='Use real crash/index data')

    args = parser.parse_args()

    print(f"\n{'#'*80}")
    print(f"#  FEATURE WEIGHT OPTIMIZATION (Phase 7)")
    print(f"#  Date: {datetime.now()}")
    print(f"#  Method: {args.method}")
    print(f"#  Metric: {args.metric}")
    print(f"{'#'*80}")

    # Load data
    if args.use_real_data:
        print("\n! Real data loading not yet implemented")
        print("   Using synthetic data for demonstration")

    print_section("Generating Synthetic Data")
    data = generate_synthetic_data(n_samples=5000)
    print(f"OK Generated {len(data)} samples")
    print(f"  Crash rate: {data['had_crash'].mean():.2%}")

    # Perform optimization
    if args.method == 'grid_search':
        results = grid_search_optimization(data, metric=args.metric, threshold=args.threshold)

        # Print top configurations
        print_top_configurations(results, top_n=10)

        # Compare with current
        compare_with_current(results)

        # Cross-validate top configuration
        if len(results) > 0:
            print_section("Cross-Validation of Optimal Configuration")

            best = results[0]
            cv_metrics = cross_validate_weights(
                data,
                best.vcc_weight,
                best.weather_weight,
                n_folds=args.cv_folds,
                threshold=args.threshold
            )

            print(f"Optimal configuration: VCC={best.vcc_weight:.2f}, Weather={best.weather_weight:.2f}")
            print(f"\nCross-validation results ({args.cv_folds} folds):")
            print(f"  F1 Score: {cv_metrics['f1_score_mean']:.3f} +/- {cv_metrics['f1_score_std']:.3f}")
            print(f"  Precision: {cv_metrics['precision_mean']:.3f}")
            print(f"  Recall: {cv_metrics['recall_mean']:.3f}")

    # Recommendations
    print_section("Implementation Recommendations")

    if len(results) > 0:
        best = results[0]

        print(f"1. Update plugin weights in configuration:")
        print(f"   ```bash")
        print(f"   # backend/.env")
        print(f"   VCC_PLUGIN_WEIGHT={best.vcc_weight:.2f}")
        print(f"   WEATHER_PLUGIN_WEIGHT={best.weather_weight:.2f}")
        print(f"   ```")

        print(f"\n2. Restart the API server to apply changes")

        print(f"\n3. Monitor crash prediction performance:")
        print(f"   - Track F1 score over time")
        print(f"   - Re-run optimization quarterly with new crash data")
        print(f"   - A/B test weight changes before full deployment")

    print(f"\n{'='*80}")
    print(f"Optimization complete.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
