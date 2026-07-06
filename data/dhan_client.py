import io
import time
from typing import Dict, List, Optional, Any
import pandas as pd
import requests
from config.settings import CONFIG
from config.logging_setup import setup_logging

logger = setup_logging("dhan_client")

INSTRUMENT_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"


class DhanAPIError(Exception):
    pass


class DhanClient:
    def __init__(self):
        self.client_id = CONFIG.dhan.client_id
        self.access_token = CONFIG.dhan.access_token
        self.base_url = CONFIG.dhan.base_url
        self.session = requests.Session()
        self.session.headers.update({
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json",
        })
        self._symbol_to_id: Dict[str, str] = {}

    def _load_instrument_master(self):
        if self._symbol_to_id:
            return
        logger.info("Downloading instrument master from Dhan ...")
        resp = requests.get(INSTRUMENT_MASTER_URL, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(io.BytesIO(resp.content), encoding="utf-8-sig", low_memory=False)
        eq = df[(df["SEM_EXM_EXCH_ID"] == "NSE") & (df["SEM_INSTRUMENT_NAME"] == "EQUITY") & (df["SEM_SEGMENT"] == "E")]
        eq = eq.drop_duplicates(subset=["SEM_TRADING_SYMBOL"])
        self._symbol_to_id = dict(zip(eq["SEM_TRADING_SYMBOL"], eq["SEM_SMST_SECURITY_ID"].astype(str)))
        logger.info("Instrument master loaded: %d symbols", len(self._symbol_to_id))

    def _get_security_id(self, symbol: str) -> str:
        self._load_instrument_master()
        sid = self._symbol_to_id.get(symbol)
        if not sid:
            raise DhanAPIError(f"Security ID not found for symbol: {symbol}")
        return sid

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                 data: Optional[Dict] = None, retries: int = 3) -> Any:
        url = f"{self.base_url}{endpoint}"
        for attempt in range(retries):
            try:
                resp = self.session.request(method, url, params=params, json=data, timeout=CONFIG.dhan.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"API request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise DhanAPIError(f"Request failed after {retries} attempts: {e}")
                time.sleep(2 ** attempt)

    def _exchange_segment(self, exchange: str) -> str:
        mapping = {"NSE": "NSE_EQ", "BSE": "BSE_EQ"}
        return mapping.get(exchange, exchange)

    def _columnar_to_rows(self, data: dict) -> List[Dict]:
        if not data or not isinstance(data, dict):
            return []
        keys = ["open", "high", "low", "close", "volume", "timestamp", "open_interest"]
        rows = min((len(v) for v in data.values() if isinstance(v, list)), default=0)
        return [{k: data[k][i] for k in keys if k in data and i < len(data[k])} for i in range(rows)]

    def get_historical_daily(self, symbol: str, exchange: str = "NSE",
                             from_date: str = "", to_date: str = "") -> List[Dict]:
        payload = {
            "securityId": self._get_security_id(symbol),
            "exchangeSegment": self._exchange_segment(exchange),
            "instrument": "EQUITY",
            "intervalCode": "1d",
            "fromDate": from_date,
            "toDate": to_date,
        }
        result = self._request("POST", "/v2/charts/historical", data=payload)
        if isinstance(result, dict):
            return self._columnar_to_rows(result)
        return result or []

    def get_historical_intraday(self, symbol: str, exchange: str = "NSE",
                                interval: int = 5, from_date: str = "", to_date: str = "") -> List[Dict]:
        payload = {
            "securityId": self._get_security_id(symbol),
            "exchangeSegment": self._exchange_segment(exchange),
            "instrument": "EQUITY",
            "intervalCode": f"{interval}m",
            "fromDate": from_date,
            "toDate": to_date,
        }
        result = self._request("POST", "/v2/charts/intraday", data=payload)
        if isinstance(result, dict):
            return self._columnar_to_rows(result)
        return result or []

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Dict:
        security_id = int(self._get_security_id(symbol))
        exg = self._exchange_segment(exchange)
        payload = {exg: [security_id], "dhanClientId": self.client_id}
        result = self._request("POST", "/v2/marketfeed/quote", data=payload)
        if isinstance(result, dict):
            quote_data = result.get("data", {}).get(exg, {}).get(str(security_id), {})
            if quote_data:
                return quote_data
        return result or {}

    def get_batch_quote(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, dict]:
        self._load_instrument_master()
        exg = self._exchange_segment(exchange)
        ids = []
        symbol_to_sid = {}
        for sym in symbols:
            sid_str = self._symbol_to_id.get(sym)
            if sid_str:
                sid = int(sid_str)
                ids.append(sid)
                symbol_to_sid[sid] = sym
        if not ids:
            return {}
        result = self._request("POST", "/v2/marketfeed/quote",
                               data={exg: ids, "dhanClientId": self.client_id})
        out: Dict[str, dict] = {}
        if isinstance(result, dict):
            exchange_data = result.get("data", {}).get(exg, {})
            for sid_str, data in exchange_data.items():
                sym = symbol_to_sid.get(int(sid_str))
                if sym and isinstance(data, dict):
                    price = 0.0
                    for key in ("last_price", "lastPrice", "ltp", "close", "CMP"):
                        val = data.get(key)
                        if val and float(val) > 0:
                            price = float(val)
                            break
                    oi = data.get("open_interest", 0) or 0
                    out[sym] = {"price": price, "oi": int(oi)}
        return out

    def get_option_chain(self, symbol: str, exchange: str = "NSE", expiry: str = "") -> List[Dict]:
        sid = int(self._get_security_id(symbol))
        if not expiry:
            expiry = self._get_nearest_expiry(sid, exchange)
        payload = {
            "UnderlyingScrip": sid,
            "UnderlyingSeg": self._exchange_segment(exchange),
            "Expiry": expiry,
        }
        result = self._request("POST", "/v2/optionchain", data=payload)
        if isinstance(result, dict):
            oc = result.get("data", {}).get("oc", {})
            chain = []
            for strike, sides in oc.items():
                for opt_type in ("ce", "pe"):
                    opt = sides.get(opt_type)
                    if opt:
                        opt["strike_price"] = float(strike)
                        opt["option_type"] = opt_type.upper()
                        opt["open_interest"] = opt.get("oi", 0) or 0
                        opt["change_oi"] = (opt.get("oi", 0) or 0) - (opt.get("previous_oi", 0) or 0)
                        opt["iv"] = opt.get("implied_volatility", 0) or 0
                        chain.append(opt)
            return chain
        return []

    def _get_nearest_expiry(self, security_id: int, exchange: str = "NSE") -> str:
        result = self._request("POST", "/v2/optionchain/expirylist",
                               data={"UnderlyingScrip": security_id,
                                     "UnderlyingSeg": self._exchange_segment(exchange)})
        if isinstance(result, dict):
            expiries = result.get("data", [])
            if expiries:
                return expiries[0]
        return ""

    def get_futures_data(self, symbol: str, exchange: str = "NSE") -> Dict:
        return self._request("GET", "/v2/futures", params={"symbol": symbol, "exchange": exchange})

    def get_open_interest(self, symbol: str, exchange: str = "NSE") -> Dict:
        return self._request("GET", "/v2/oi", params={"symbol": symbol, "exchange": exchange})

    def get_market_status(self) -> Dict:
        return self._request("GET", "/v2/marketStatus")

    def get_mwpl(self, symbol: str) -> Dict:
        return self._request("GET", "/v2/mwpl", params={"symbol": symbol})

    def get_corporate_actions(self, symbol: str) -> List[Dict]:
        return self._request("GET", "/v2/corporateActions", params={"symbol": symbol}).get("data", [])

    def get_security_info(self, symbol: str, exchange: str = "NSE") -> Dict:
        return self._request("GET", "/v2/securities", params={"symbol": symbol, "exchange": exchange})
