# spc_http_server.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading
import time
import numpy as np
import typing as t
import bh_spc
from bh_spc import spcm

# ---------- globals ----------
_spc_lock = threading.Lock()
_initialized = False
_mod_no_default = 1  # default module number only

# store last set parameters (no defaults except module)
CURRENT_PARAMS: dict = {}  # keys are parameter names (str) -> values

# ---------- Pydantic models ----------
class SetParamReq(BaseModel):
    name: str
    value: t.Union[int, float, str]
    mod_no: int = _mod_no_default

class MeasureReq(BaseModel):
    duration: float  # seconds
    mode: t.Optional[int] = None  # 0=T2(hist), 1=T3(FIFO). If omitted, use CURRENT_PARAMS['MODE'] or default 1
    tac_range: t.Optional[float] = None  # ns, used to build histogram if needed
    bins: t.Optional[int] = 64
    mod_no: int = _mod_no_default

class GetParamReq(BaseModel):
    name: str
    mod_no: int = _mod_no_default

app = FastAPI(title="SPC HTTP Server (pybhspc wrapper)")

# ---------- helper functions ----------
def init_spc():
    """Initialize SPC via bh_spc; idempotent and locked."""
    global _initialized
    with _spc_lock:
        if _initialized:
            return
        # Use minimal ini similar to interactive code
        with bh_spc.ini_file(bh_spc.minimal_spcm_ini(spcm.DLLOperationMode.HARDWARE)) as ini:
            spcm.init(ini)
        _initialized = True

def close_spc():
    global _initialized
    with _spc_lock:
        if _initialized:
            try:
                spcm.close()
            finally:
                _initialized = False

def set_spc_parameter(mod_no: int, name: str, value):
    """Set SPC parameter using spcm.ParID lookup. Raises ValueError if name invalid."""
    # Normalize name: pybhspc uses ParID attributes like CFD_LIMIT_LOW, TAC_RANGE, etc.
    key = name if isinstance(name, str) else str(name)
    key = key.strip()
    # Some callers use different naming, allow uppercase
    key_up = key.upper()

    if not hasattr(spcm.ParID, key_up):
        raise ValueError(f"Unknown parameter name '{name}' (not in spcm.ParID)")
    parid = getattr(spcm.ParID, key_up)
    # Cast value to primitive Python type expected by wrapper
    # spcm.set_parameter will likely accept Python int/float
    spcm.set_parameter(mod_no, parid, value)
    # remember it
    CURRENT_PARAMS[key_up] = value

def _safe_configure_memory_if_exists(mod_no: int):
    """Call configure_memory if available on wrapper to apply mode/memory changes."""
    try:
        if hasattr(spcm, "configure_memory"):
            # signature may differ; call with safe defaults if possible
            # try common signatures
            try:
                spcm.configure_memory(mod_no, 0)
            except TypeError:
                try:
                    spcm.configure_memory(mod_no)
                except Exception:
                    pass
    except Exception:
        # ignore errors here; actual measurement will surface issues in a controlled try/except
        pass

def read_fifo_microtimes(mod_no: int, duration_s: float, buf_size: int = 32768) -> np.ndarray:
    """Read FIFO microtime records (T3 / FIFO). Returns numpy array of microtime values."""
    # We lock around sequence of start/read/stop to avoid concurrent access
    with _spc_lock:
        spcm.start_measurement(mod_no)

    start_time = time.monotonic()
    chunks = []
    try:
        while time.monotonic() - start_time < duration_s:
            with _spc_lock:
                buf = spcm.read_fifo_to_array(mod_no, buf_size)
            if len(buf):
                chunks.append(buf)
            # avoid busy loop
            if len(buf) < buf_size:
                time.sleep(0.001)

        # drain remaining
        while True:
            with _spc_lock:
                buf = spcm.read_fifo_to_array(mod_no, buf_size)
            if not len(buf):
                break
            chunks.append(buf)
    finally:
        with _spc_lock:
            try:
                spcm.stop_measurement(mod_no)
            except Exception:
                pass

    if not chunks:
        raise RuntimeError("No data collected from SPC FIFO.")

    records = np.concatenate(chunks).view(np.uint32)
    # Filter photon records (per your earlier decoding)
    photons = np.extract(np.bitwise_and(records, (0b1001 << 28)) == 0, records)
    micro = np.bitwise_and(np.right_shift(photons, 16), (1 << 12) - 1)
    micro = (1 << 12) - 1 - micro
    return micro

def read_histogram_via_wrapper(mod_no: int, duration_s: float) -> np.ndarray:
    """T2 histogram acquisition. Use wrapper histogram call if available, else emulate."""
    # Some wrappers provide read_histogram or fill_memory + read_data_page.
    # Try to use `spcm.read_histogram` if present, else do start/stop + read_fifo and bin.
    # We'll try safe methods and raise if unsupported.
    # Start measurement (histogram mode)
    with _spc_lock:
        spcm.start_measurement(mod_no)
    time.sleep(duration_s)
    with _spc_lock:
        try:
            spcm.stop_measurement(mod_no)
        except Exception:
            pass

        # Prefer direct histogram read if available
        if hasattr(spcm, "read_histogram"):
            hist = spcm.read_histogram(mod_no)
            # Ensure numpy array
            return np.array(hist, dtype=np.int64)
        # try read_data_page or similar
        if hasattr(spcm, "read_data_page"):
            # read_data_page signature may vary; attempt commonly used form:
            try:
                page = spcm.read_data_page(mod_no, 0)  # channel/page 0
                return np.array(page, dtype=np.int64)
            except TypeError:
                # fallback
                pass
        # fallback: if nothing else, try to read FIFO and then histogram it
        micro = read_fifo_microtimes(mod_no, duration_s)
        return micro  # caller will histogram if needed

def histogram_from_microtimes(microtimes: np.ndarray, tac_range_ns: float, bins: int = 64):
    times_ns = microtimes * (tac_range_ns / 4096.0)
    bin_edges = np.linspace(0.0, tac_range_ns, bins + 1)
    counts, _ = np.histogram(times_ns, bins=bin_edges)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    return bin_centers.tolist(), counts.tolist()

# ---------- FastAPI lifespan (startup/shutdown) ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_spc()
    yield
    # shutdown
    close_spc()

app = FastAPI(lifespan=lifespan)

# ---------- API endpoints ----------
@app.post("/set_parameter")
def api_set_parameter(req: SetParamReq):
    """Set one SPC parameter. name must match attribute in spcm.ParID (case-insensitive)."""
    try:
        init_spc()
        # apply and remember
        set_spc_parameter(req.mod_no, req.name, req.value)
        # try to apply memory changes if MODE changed
        if req.name.strip().upper() == "MODE":
            _safe_configure_memory_if_exists(req.mod_no)
        return {"status": "ok", "message": f"Parameter {req.name} set to {req.value}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/get_parameter")
def api_get_parameter(name: str, mod_no: int = _mod_no_default):
    """Return the last set value for a parameter (from CURRENT_PARAMS) if available."""
    try:
        init_spc()
        k = name.strip().upper()
        if k in CURRENT_PARAMS:
            return {"status": "ok", "name": k, "value": CURRENT_PARAMS[k]}
        # fallback: try to read parameter from device if wrapper exposes getter
        if hasattr(spcm, "get_parameter"):
            try:
                val = spcm.get_parameter(mod_no, getattr(spcm.ParID, k))
                return {"status": "ok", "name": k, "value": val}
            except Exception:
                pass
        return {"status": "error", "message": f"No stored value for {name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/measure")
def api_measure(req: MeasureReq):
    """
    Trigger a measurement.
    - duration: seconds (required)
    - mode: optional (0=T2 histogram, 1=T3 FIFO). If omitted uses CURRENT_PARAMS['MODE'] if set, else defaults to 1 (FIFO)
    - tac_range: used for histogram binning if needed
    - bins: number of bins for histogram
    """
    init_spc()
    mod_no = req.mod_no
    duration = float(req.duration)
    mode = req.mode if req.mode is not None else int(CURRENT_PARAMS.get("MODE", 1))
    tac_range = req.tac_range if req.tac_range is not None else float(CURRENT_PARAMS.get("TAC_RANGE", 50.0))
    bins = int(req.bins or 64)

    # Validate mode
    if mode not in (0, 1):
        return {"status": "error", "message": "mode must be 0 (T2 histogram) or 1 (T3 FIFO)"}

    # Apply current params to device before measure (if any)
    # NOTE: we do not assume many defaults; user should set parameters from Debian via /set_parameter
    if CURRENT_PARAMS:
        try:
            # set all known parameters to device (safe to repeat)
            with _spc_lock:
                for name, value in CURRENT_PARAMS.items():
                    # skip MODE here because user might pass mode in this request explicitly,
                    # but it's safe to set anyway
                    if hasattr(spcm.ParID, name):
                        spcm.set_parameter(mod_no, getattr(spcm.ParID, name), value)
        except Exception as e:
            return {"status": "error", "message": f"Failed to apply stored parameters: {e}"}

    # If user explicitly set MODE in stored params or request, attempt to configure memory
    try:
        if hasattr(spcm.ParID, "MODE"):
            # set mode on device as last step before measurement
            try:
                with _spc_lock:
                    spcm.set_parameter(mod_no, getattr(spcm.ParID, "MODE"), int(mode))
            except Exception:
                pass
            _safe_configure_memory_if_exists(mod_no)
    except Exception:
        pass

    # Now perform mode-specific measurement
    try:
        if mode == 1:
            # T3 FIFO mode -> read microtimes
            micro = read_fifo_microtimes(mod_no, duration)
            # return first N microtimes and length and optionally histogram if user asked
            response = {
                "status": "ok",
                "mode": mode,
                "n_events": int(len(micro)),
                "microtimes_sample": micro[:200].tolist() if len(micro) > 0 else [],
            }
            # optionally provide histogram too (we do not auto-build unless requested; but we can)
            bin_centers, counts = histogram_from_microtimes(micro, tac_range, bins=bins)
            response["bin_centers"] = bin_centers
            response["counts"] = counts
            return response

        else:
            # mode == 0 -> T2 histogram mode
            hist_data = read_histogram_via_wrapper(mod_no, duration)
            # If read_histogram returned microtimes fallback, histogram them
            if hist_data.ndim == 1 and hist_data.dtype == np.int64:
                # if this is histogram array (counts per channel), use it directly
                if hist_data.size > 1000:  # heuristic: SPI histogram length large -> already histogram
                    counts = hist_data.tolist()
                    # build bin centers assuming tac_range and length
                    bin_edges = np.linspace(0.0, tac_range, len(counts) + 1)
                    bin_centers = (0.5 * (bin_edges[:-1] + bin_edges[1:])).tolist()
                else:
                    # treat as microtimes and histogram them
                    bin_centers, counts = histogram_from_microtimes(hist_data, tac_range, bins=bins)
            else:
                # Unlikely, but ensure list conversion
                counts = np.array(hist_data).tolist()
                bin_edges = np.linspace(0.0, tac_range, len(counts) + 1)
                bin_centers = (0.5 * (bin_edges[:-1] + bin_edges[1:])).tolist()

            return {"status": "ok", "mode": mode, "bin_centers": bin_centers, "counts": counts}

    except Exception as e:
        # catch wrapper exceptions and return safe message
        return {"status": "error", "message": str(e)}

@app.get("/status")
def api_status():
    init_spc()
    return {"status": "ok", "initialized": _initialized, "stored_params_count": len(CURRENT_PARAMS)}

# ---------- run with uvicorn externally ----------
# uvicorn spc_http_server:app --host 0.0.0.0 --port 8000
