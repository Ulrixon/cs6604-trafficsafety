import requests
import sys


def test_bsm_data():
    url = "http://localhost:8000/api/v1/database/data/bsm?limit=5"
    print(f"Fetching {url}...")
    try:
        resp = requests.get(url)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Success. Got {len(data)} rows.")
            if data:
                print("First row keys:", data[0].keys())
        else:
            print("Error:", resp.text)
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    test_bsm_data()
