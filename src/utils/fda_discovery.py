import requests
from typing import Optional, Dict

def find_510k_for_product(name: str) -> Optional[Dict]:
    try:
        url = "https://api.fda.gov/device/510k.json"
        params = {"search": f'device_name:"{name}"', "limit": 1}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            items = (r.json() or {}).get("results") or []
            return items[0] if items else None
    except Exception:
        pass
    return None

def make_510k_record_urls(k_number: str) -> Dict[str, str]:
    k = k_number.upper().replace("K", "")
    return {
        "search": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K{k}",
        "alt_search": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?knumber=K{k}",
    }