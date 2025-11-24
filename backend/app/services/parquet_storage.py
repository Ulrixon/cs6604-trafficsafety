"""
Parquet storage service for saving and loading historical features and indices.

Provides efficient columnar storage with date-based partitioning for fast
querying of historical safety index data.
"""

import os
import pandas as pd
from pathlib import Path
from typing import Optional, List
from datetime import datetime, date, timedelta
from ..core.config import settings


class ParquetStorage:
    """
    Service for managing Parquet file storage of features and indices.
    
    Organizes data by date in partitioned directories for efficient querying.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize Parquet storage service.

        Args:
            storage_path: Base path for Parquet storage (defaults to settings.PARQUET_STORAGE_PATH)
        """
        self.base_path = Path(storage_path or settings.PARQUET_STORAGE_PATH)
        self.features_path = self.base_path / "features"
        self.indices_path = self.base_path / "indices"
        self.constants_path = self.base_path / "constants"
        self.raw_bsm_path = self.base_path / "raw" / "bsm"
        self.raw_psm_path = self.base_path / "raw" / "psm"
        self.raw_mapdata_path = self.base_path / "raw" / "mapdata"
        self.weather_path = self.base_path / "weather"

        # Create directories if they don't exist
        self.features_path.mkdir(parents=True, exist_ok=True)
        self.indices_path.mkdir(parents=True, exist_ok=True)
        self.constants_path.mkdir(parents=True, exist_ok=True)
        self.raw_bsm_path.mkdir(parents=True, exist_ok=True)
        self.raw_psm_path.mkdir(parents=True, exist_ok=True)
        self.raw_mapdata_path.mkdir(parents=True, exist_ok=True)
        self.weather_path.mkdir(parents=True, exist_ok=True)
    
    def save_features(self, dataframe: pd.DataFrame, target_date: Optional[date] = None) -> str:
        """
        Save aggregated features to Parquet file.
        
        Args:
            dataframe: DataFrame with features (must have time_15min column)
            target_date: Target date for file naming (defaults to first date in dataframe)
            
        Returns:
            Path to saved file
        """
        if len(dataframe) == 0:
            raise ValueError("Cannot save empty dataframe")
        
        # Determine date from dataframe if not provided
        if target_date is None:
            if 'time_15min' not in dataframe.columns:
                target_date = date.today()
            else:
                target_date = pd.to_datetime(dataframe['time_15min'].iloc[0]).date()
        
        filename = f"features_{target_date.strftime('%Y-%m-%d')}.parquet"
        filepath = self.features_path / filename
        
        # Ensure time_15min is datetime
        df = dataframe.copy()
        if 'time_15min' in df.columns:
            df['time_15min'] = pd.to_datetime(df['time_15min'])
        
        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')
        
        return str(filepath)
    
    def save_indices(self, dataframe: pd.DataFrame, target_date: Optional[date] = None) -> str:
        """
        Save computed safety indices to Parquet file.
        
        Args:
            dataframe: DataFrame with indices (must have time_15min column)
            target_date: Target date for file naming (defaults to first date in dataframe)
            
        Returns:
            Path to saved file
        """
        if len(dataframe) == 0:
            raise ValueError("Cannot save empty dataframe")
        
        # Determine date from dataframe if not provided
        if target_date is None:
            if 'time_15min' not in dataframe.columns:
                target_date = date.today()
            else:
                target_date = pd.to_datetime(dataframe['time_15min'].iloc[0]).date()
        
        filename = f"indices_{target_date.strftime('%Y-%m-%d')}.parquet"
        filepath = self.indices_path / filename
        
        # Ensure time_15min is datetime
        df = dataframe.copy()
        if 'time_15min' in df.columns:
            df['time_15min'] = pd.to_datetime(df['time_15min'])
        
        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')
        
        return str(filepath)
    
    def save_normalization_constants(self, constants: dict) -> str:
        """
        Save normalization constants to Parquet file.

        Args:
            constants: Dictionary of normalization constants

        Returns:
            Path to saved file
        """
        # Convert to DataFrame for consistent storage
        df = pd.DataFrame([constants])
        filepath = self.constants_path / "normalization_constants.parquet"

        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')

        return str(filepath)

    def save_bsm_batch(self, bsm_messages: List[dict], target_date: Optional[date] = None) -> str:
        """
        Save raw BSM messages to Parquet file.

        Args:
            bsm_messages: List of BSM message dictionaries from VCC API
            target_date: Target date for file naming (defaults to today)

        Returns:
            Path to saved file
        """
        if not bsm_messages:
            raise ValueError("Cannot save empty BSM batch")

        # Convert to DataFrame
        df = pd.DataFrame(bsm_messages)

        # Use current date if not provided
        if target_date is None:
            target_date = date.today()

        # Create timestamp-based filename for this batch
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"bsm_{target_date.strftime('%Y-%m-%d')}_{timestamp}.parquet"
        filepath = self.raw_bsm_path / filename

        print(f"DEBUG: Saving BSM to: {filepath}")
        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')
        print(f"DEBUG: Successfully saved to: {filepath}")

        return str(filepath)

    def save_psm_batch(self, psm_messages: List[dict], target_date: Optional[date] = None) -> str:
        """
        Save raw PSM messages to Parquet file.

        Args:
            psm_messages: List of PSM message dictionaries from VCC API
            target_date: Target date for file naming (defaults to today)

        Returns:
            Path to saved file
        """
        if not psm_messages:
            raise ValueError("Cannot save empty PSM batch")

        # Convert to DataFrame
        df = pd.DataFrame(psm_messages)

        # Use current date if not provided
        if target_date is None:
            target_date = date.today()

        # Create timestamp-based filename for this batch
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"psm_{target_date.strftime('%Y-%m-%d')}_{timestamp}.parquet"
        filepath = self.raw_psm_path / filename

        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')

        return str(filepath)

    def save_mapdata_batch(self, mapdata_messages: List[dict], target_date: Optional[date] = None) -> str:
        """
        Save raw MapData messages to Parquet file.

        Args:
            mapdata_messages: List of MapData message dictionaries from VCC API
            target_date: Target date for file naming (defaults to today)

        Returns:
            Path to saved file
        """
        if not mapdata_messages:
            raise ValueError("Cannot save empty MapData batch")

        # Convert to DataFrame
        df = pd.DataFrame(mapdata_messages)

        # Use current date if not provided
        if target_date is None:
            target_date = date.today()

        # Create timestamp-based filename for this batch
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"mapdata_{target_date.strftime('%Y-%m-%d')}_{timestamp}.parquet"
        filepath = self.raw_mapdata_path / filename

        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')

        return str(filepath)

    def save_weather_observations(self, dataframe: pd.DataFrame, target_date: Optional[date] = None) -> str:
        """
        Save weather observations to Parquet file.

        Args:
            dataframe: DataFrame with weather observations (must have observation_time column)
            target_date: Target date for file naming (defaults to first date in dataframe)

        Returns:
            Path to saved file

        Example:
            ```python
            weather_df = pd.DataFrame([
                {
                    'station_id': 'KRIC',
                    'observation_time': datetime(2024, 11, 21, 14, 0),
                    'temperature_c': 18.3,
                    'precipitation_mm': 2.5,
                    'temperature_normalized': 0.1
                }
            ])
            path = storage.save_weather_observations(weather_df)
            ```
        """
        if len(dataframe) == 0:
            raise ValueError("Cannot save empty weather dataframe")

        # Determine date from dataframe if not provided
        if target_date is None:
            if 'observation_time' not in dataframe.columns:
                target_date = date.today()
            else:
                target_date = pd.to_datetime(dataframe['observation_time'].iloc[0]).date()

        filename = f"weather_{target_date.strftime('%Y-%m-%d')}.parquet"
        filepath = self.weather_path / filename

        # Ensure observation_time is datetime
        df = dataframe.copy()
        if 'observation_time' in df.columns:
            df['observation_time'] = pd.to_datetime(df['observation_time'])

        df.to_parquet(filepath, engine='pyarrow', index=False, compression='snappy')

        return str(filepath)

    def save_safety_indices(self, dataframe: pd.DataFrame, target_date: Optional[date] = None) -> str:
        """
        Alias for save_indices for backwards compatibility.
        """
        return self.save_indices(dataframe, target_date)

    def load_features(self, start_date: date, end_date: date, 
                     intersection_id: Optional[str] = None) -> pd.DataFrame:
        """
        Load features from Parquet files for date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            intersection_id: Optional intersection filter
            
        Returns:
            Combined DataFrame with features from date range
        """
        dataframes = []
        current_date = start_date
        
        while current_date <= end_date:
            filename = f"features_{current_date.strftime('%Y-%m-%d')}.parquet"
            filepath = self.features_path / filename
            
            if filepath.exists():
                try:
                    df = pd.read_parquet(filepath, engine='pyarrow')
                    
                    # Filter by intersection if specified
                    if intersection_id and 'intersection' in df.columns:
                        df = df[df['intersection'] == intersection_id]
                    
                    # Filter by date range (handle partial days)
                    if 'time_15min' in df.columns:
                        df['time_15min'] = pd.to_datetime(df['time_15min'])
                        start_dt = pd.Timestamp(start_date)
                        end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
                        df = df[(df['time_15min'] >= start_dt) & (df['time_15min'] < end_dt)]
                    
                    if len(df) > 0:
                        dataframes.append(df)
                except Exception as e:
                    print(f"⚠ Error loading {filename}: {e}")
            
            current_date += timedelta(days=1)
        
        if not dataframes:
            return pd.DataFrame()
        
        return pd.concat(dataframes, ignore_index=True)
    
    def load_indices(self, start_date: date, end_date: date,
                    intersection_id: Optional[str] = None) -> pd.DataFrame:
        """
        Load safety indices from Parquet files for date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            intersection_id: Optional intersection filter
            
        Returns:
            Combined DataFrame with indices from date range
        """
        dataframes = []
        current_date = start_date
        
        while current_date <= end_date:
            filename = f"indices_{current_date.strftime('%Y-%m-%d')}.parquet"
            filepath = self.indices_path / filename
            
            if filepath.exists():
                try:
                    df = pd.read_parquet(filepath, engine='pyarrow')
                    
                    # Filter by intersection if specified
                    if intersection_id and 'intersection' in df.columns:
                        df = df[df['intersection'] == intersection_id]
                    
                    # Filter by date range (handle partial days)
                    if 'time_15min' in df.columns:
                        df['time_15min'] = pd.to_datetime(df['time_15min'])
                        start_dt = pd.Timestamp(start_date)
                        end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
                        df = df[(df['time_15min'] >= start_dt) & (df['time_15min'] < end_dt)]
                    
                    if len(df) > 0:
                        dataframes.append(df)
                except Exception as e:
                    print(f"⚠ Error loading {filename}: {e}")
            
            current_date += timedelta(days=1)
        
        if not dataframes:
            return pd.DataFrame()
        
        return pd.concat(dataframes, ignore_index=True)
    
    def load_weather_observations(
        self,
        start_date: date,
        end_date: date,
        station_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load weather observations from Parquet files for date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            station_id: Optional station filter (e.g., 'KRIC')

        Returns:
            Combined DataFrame with weather observations from date range

        Example:
            ```python
            weather_data = storage.load_weather_observations(
                date(2024, 11, 21),
                date(2024, 11, 23),
                station_id='KRIC'
            )
            ```
        """
        dataframes = []
        current_date = start_date

        while current_date <= end_date:
            filename = f"weather_{current_date.strftime('%Y-%m-%d')}.parquet"
            filepath = self.weather_path / filename

            if filepath.exists():
                try:
                    df = pd.read_parquet(filepath, engine='pyarrow')

                    # Filter by station if specified
                    if station_id and 'station_id' in df.columns:
                        df = df[df['station_id'] == station_id]

                    # Filter by date range (handle partial days)
                    if 'observation_time' in df.columns:
                        df['observation_time'] = pd.to_datetime(df['observation_time'])
                        start_dt = pd.Timestamp(start_date)
                        end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
                        df = df[(df['observation_time'] >= start_dt) & (df['observation_time'] < end_dt)]

                    if len(df) > 0:
                        dataframes.append(df)
                except Exception as e:
                    print(f"⚠ Error loading {filename}: {e}")

            current_date += timedelta(days=1)

        if not dataframes:
            return pd.DataFrame()

        return pd.concat(dataframes, ignore_index=True)

    def load_normalization_constants(self) -> dict:
        """
        Load normalization constants from Parquet file.

        Returns:
            Dictionary of normalization constants
        """
        filepath = self.constants_path / "normalization_constants.parquet"

        if not filepath.exists():
            return {}

        try:
            df = pd.read_parquet(filepath, engine='pyarrow')
            if len(df) > 0:
                return df.iloc[0].to_dict()
            return {}
        except Exception as e:
            print(f"⚠ Error loading normalization constants: {e}")
            return {}
    
    def list_available_dates(self, data_type: str = 'features') -> List[date]:
        """
        List all dates with available data.
        
        Args:
            data_type: Type of data ('features' or 'indices')
            
        Returns:
            List of dates with available data files
        """
        if data_type == 'features':
            path = self.features_path
            prefix = "features_"
        elif data_type == 'indices':
            path = self.indices_path
            prefix = "indices_"
        else:
            raise ValueError(f"Unknown data_type: {data_type}")
        
        dates = []
        for filepath in path.glob(f"{prefix}*.parquet"):
            try:
                # Extract date from filename: features_YYYY-MM-DD.parquet
                date_str = filepath.stem.replace(prefix, "")
                dates.append(datetime.strptime(date_str, '%Y-%m-%d').date())
            except ValueError:
                continue
        
        return sorted(dates)


# Global storage instance
parquet_storage = ParquetStorage()

