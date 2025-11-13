"""
Helper script to extract JWT token from Trino OAuth2 session.
Run this on your host machine (where you have browser access) to get a token for Docker.

Usage:
    python extract_trino_token.py
"""

import json
import os
from pathlib import Path
from trino import dbapi
from trino.auth import OAuth2Authentication

def get_token_cache_path():
    """Get the Trino token cache file path"""
    home = Path.home()
    token_cache = home / ".trino" / "token-cache.json"
    return token_cache

def authenticate_and_get_token():
    """Authenticate with Trino and extract the JWT token"""
    print("Connecting to Trino with OAuth2...")
    print("A browser window will open for authentication.\n")

    # Create connection (this will trigger OAuth flow)
    conn = dbapi.connect(
        host="smart-cities-trino.pre-prod.cloud.vtti.vt.edu",
        port=443,
        http_scheme="https",
        auth=OAuth2Authentication(),
        catalog="smartcities_iceberg",
    )

    # Execute a simple query to ensure authentication completes
    cur = conn.cursor()
    cur.execute("SELECT 1")
    result = cur.fetchone()

    print("✓ Authentication successful!\n")

    # Try to extract token from cache
    token_cache = get_token_cache_path()

    if token_cache.exists():
        print(f"Token cache found at: {token_cache}")
        try:
            with open(token_cache, 'r') as f:
                cache_data = json.load(f)

            # The structure varies, but typically contains access_token
            if isinstance(cache_data, dict):
                # Look for token in various possible locations
                token = None

                # Check common locations
                for key in cache_data:
                    if isinstance(cache_data[key], dict):
                        if 'access_token' in cache_data[key]:
                            token = cache_data[key]['access_token']
                            break
                        if 'token' in cache_data[key]:
                            token = cache_data[key]['token']
                            break

                if not token and 'access_token' in cache_data:
                    token = cache_data['access_token']

                if token:
                    print("\n" + "="*80)
                    print("JWT TOKEN FOUND")
                    print("="*80)
                    print("\nAdd this to your .env file:")
                    print(f"\nTRINO_JWT_TOKEN={token}\n")
                    print("="*80)

                    # Also save to a file for easy copying
                    token_file = Path("trino_jwt_token.txt")
                    with open(token_file, 'w') as f:
                        f.write(token)
                    print(f"\n✓ Token also saved to: {token_file.absolute()}")

                    return token
                else:
                    print("\n⚠ Token cache exists but couldn't find access_token")
                    print(f"Cache contents: {json.dumps(cache_data, indent=2)[:500]}...")

        except Exception as e:
            print(f"\n⚠ Error reading token cache: {e}")
    else:
        print(f"\n⚠ Token cache not found at: {token_cache}")

    print("\n" + "="*80)
    print("ALTERNATIVE: Use Token Cache Mounting")
    print("="*80)
    print("\nIf JWT extraction doesn't work, your docker-compose.yml is already")
    print("configured to mount the token cache directory:")
    print(f"  Host: {token_cache.parent}")
    print(f"  Container: /root/.trino/")
    print("\nJust run: docker-compose up --build")
    print("="*80)

    return None

def main():
    print("\n" + "="*80)
    print("TRINO JWT TOKEN EXTRACTOR")
    print("="*80)
    print("\nThis script will:")
    print("1. Authenticate you with Trino via OAuth2 (browser required)")
    print("2. Extract the JWT token from the cached session")
    print("3. Save it for use in Docker\n")

    input("Press Enter to continue...")

    token = authenticate_and_get_token()

    if not token:
        print("\n" + "="*80)
        print("TOKEN EXTRACTION FAILED")
        print("="*80)
        print("\nOptions:")
        print("1. Your docker-compose.yml already mounts the token cache directory")
        print("   Just run: docker-compose up --build")
        print("\n2. Contact your Trino admin to get OAuth2 credentials for JWT auth")
        print("   You'll need: client_id and client_secret")
        print("\n3. Use the Jupyter notebook authentication (it already works!)")
        print("="*80)

if __name__ == "__main__":
    main()
