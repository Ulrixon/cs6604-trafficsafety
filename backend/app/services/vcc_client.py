"""
VCC API client for querying Virginia Connected Corridor data.

Handles JWT authentication and provides methods for accessing BSM, PSM, SPAT,
and MapData endpoints from the VCC Public API v3.1.
"""

import requests
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import time
from ..core.config import settings


class VCCClient:
    """
    Client for interacting with VCC Public API.
    
    Handles JWT token management, rate limiting, and provides methods for
    all VCC API endpoints.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize VCC API client.
        
        Args:
            base_url: VCC API base URL (defaults to settings.VCC_BASE_URL)
            client_id: OAuth2 client ID (defaults to settings.VCC_CLIENT_ID)
            client_secret: OAuth2 client secret (defaults to settings.VCC_CLIENT_SECRET)
        """
        self.base_url = base_url or settings.VCC_BASE_URL
        self.client_id = client_id or settings.VCC_CLIENT_ID
        self.client_secret = client_secret or settings.VCC_CLIENT_SECRET
        self.token_url = f"{self.base_url}/api/auth/client"
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._last_request_time: Optional[float] = None
        self._min_request_interval = 0.1  # Rate limiting: 100ms between requests
        
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        if self._last_request_time:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get or refresh JWT access token.
        
        Args:
            force_refresh: Force token refresh even if current token is valid
            
        Returns:
            Access token string or None if authentication fails
        """
        # Check if current token is still valid
        if not force_refresh and self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):  # Refresh 5 min early
                return self._access_token
        
        if not self.client_id or not self.client_secret:
            raise ValueError("VCC_CLIENT_ID and VCC_CLIENT_SECRET must be set")
        
        self._rate_limit()
        
        try:
            response = requests.post(
                self.token_url,
                data={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                allow_redirects=False,
                timeout=10
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 36000)  # Default 10 hours
            
            # Store expiration time
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            return self._access_token
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get VCC access token: {e}")
            return None
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get authorization headers with current token"""
        token = self.get_access_token()
        if not token:
            raise RuntimeError("Failed to obtain VCC API access token")
        return {'Authorization': f'Bearer {token}'}
    
    def get_mapdata(self, intersection_id: Optional[int] = None, decoded: bool = True) -> List[Dict[str, Any]]:
        """
        Get MapData messages describing intersection lane geometry.
        
        Args:
            intersection_id: Specific intersection ID, or None for all intersections
            decoded: If True, return decoded JSON format; if False, return raw format
            
        Returns:
            List of MapData messages
        """
        self._rate_limit()
        
        if intersection_id:
            url = f"{self.base_url}/api/mapdata/{intersection_id}/{'decoded' if decoded else 'raw'}"
        else:
            url = f"{self.base_url}/api/mapdata/{'decoded' if decoded else 'raw'}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else [data]
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get MapData: {e}")
            return []
    
    def get_bsm_current(self) -> List[Dict[str, Any]]:
        """
        Get current BSM (Basic Safety Message) messages.
        
        Returns:
            List of BSM messages with vehicle position and movement data
        """
        self._rate_limit()
        
        url = f"{self.base_url}/api/bsm/current"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get BSM: {e}")
            return []
    
    def get_psm_current(self) -> List[Dict[str, Any]]:
        """
        Get current PSM (Personal Safety Message) messages for VRUs.
        
        Returns:
            List of PSM messages with pedestrian/cyclist position and movement data
        """
        self._rate_limit()
        
        url = f"{self.base_url}/api/psm/current"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get PSM: {e}")
            return []
    
    def get_spat(self, intersection_id: str = 'all', format_type: str = 'JSON_COMPLETE') -> List[str]:
        """
        Get latest SPAT (Signal Phase and Timing) messages.
        
        Args:
            intersection_id: Intersection ID or 'all' for all intersections
            format_type: Format type ('JSON_COMPLETE' or 'JSON')
            
        Returns:
            List of SPAT message strings (JSON format)
        """
        self._rate_limit()
        
        url = f"{self.base_url}/api/spat?format={format_type}"
        if intersection_id != 'all':
            url = f"{self.base_url}/api/spat/{intersection_id}?format={format_type}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get SPAT: {e}")
            return []
    
    def get_websocket_key(self, message_type: str = 'bsm') -> Optional[str]:
        """
        Get WebSocket key for streaming real-time messages.
        
        Args:
            message_type: Type of message ('bsm' or 'psm')
            
        Returns:
            WebSocket key string or None if request fails
        """
        self._rate_limit()
        
        url = f"{self.base_url}/api/{message_type}/key"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            key = response.content.decode('utf-8')
            return key
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get WebSocket key for {message_type}: {e}")
            return None
    
    def get_websocket_url(self, message_type: str = 'bsm', intersection_id: str = 'all', 
                         format_type: str = 'JSON_COMPLETE') -> Optional[str]:
        """
        Get WebSocket URL for streaming messages.
        
        Args:
            message_type: Type of message ('bsm', 'psm', or 'spat')
            intersection_id: Intersection ID or 'all'
            format_type: Format type ('JSON_COMPLETE' or 'JSON')
            
        Returns:
            Full WebSocket URL (wss://) or None if request fails
        """
        self._rate_limit()
        
        if message_type == 'spat':
            url = f"{self.base_url}/api/spat/{intersection_id}?format={format_type}"
        else:
            # For BSM/PSM, get key first then construct URL
            key = self.get_websocket_key(message_type)
            if not key:
                return None
            return f"wss://vcc.vtti.vt.edu/ws/{message_type}?key={key}"
        
        # For SPAT, get URL from API response
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            ws_url = data.get('url')
            if ws_url:
                return f"wss://vcc.vtti.vt.edu{ws_url}"
            return None
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get WebSocket URL for {message_type}: {e}")
            return None
    
    def post_bsm_json(self, bsm_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Post a BSM message in JSON format.
        
        Args:
            bsm_data: BSM message data dictionary
            
        Returns:
            Response data or None if request fails
        """
        self._rate_limit()
        
        url = f"{self.base_url}/api/bsm/json"
        try:
            response = requests.post(url, json=bsm_data, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to post BSM: {e}")
            return None


# Global client instance
vcc_client = VCCClient()

