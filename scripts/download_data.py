"""Download the UCI Adult census extract (48,842 records) into data/raw/adult/."""
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/2/adult.zip"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "adult"

if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=120) as response:
        zipfile.ZipFile(io.BytesIO(response.read())).extractall(RAW)
    print("downloaded to", RAW)
