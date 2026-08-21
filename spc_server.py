import threading
import time
from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import bh_spc
from bh_spc import spcm

app = FastAPI()

# --- Thread safety ---
_spc_lock = threading.Lock()
_initialized = False
_mod_no = 0

# --- Parameter defaults ---
PARAM_DEFAULTS = {
    'CFD_LIMIT_LOW': -100,
    'CFD_LIMIT_HIGH': 5.02,
    'CFD_HOLDOFF': 5.0,
    'CFD_ZC_LEVEL': -5.29,
    'TAC_RANGE': 50.0,
    'TAC_LIMIT_LOW': 5.10,
    'TAC_LIMIT_HIGH': 95.29,
    'TAC_GAIN': 4,
    'TAC_OFFSET': 0.0,
    'SYNC_THRESHOLD': -70.59,
    'SYNC_HOLDOFF': 4.0,
    'SYNC_FREQ_DIV': 1,
    'SYNC_ZC_LEVEL': -5.29,
    'TRIGGER': 0,
    'STOP_ON_TIME': 1,
    'COLLECT_TIME': 0.01,
    'MODE': 1  # Default T3 (FIFO)
}

# --- Pydantic model for API ---
class SPCParams(BaseModel):
    CFD_LIMIT_LOW: float = 0.0
    CFD_LIMIT_HIGH: float = 80.0
    CFD_HOLDOFF: float = 5.0
    CFD_ZC_LEVEL: float = 0.0
    TAC_RANGE: float = 5.003e-8
    TAC_LIMIT_LOW: float = 10.0
    TAC_LIMIT_HIGH: float = 80.0
    TAC_GAIN: int = 1
    TAC_OFFSET: float = 0.0
    SYNC_THRESHOLD: float = -20.0
    SYNC_HOLDOFF: float = 4.0
    SYNC_FREQ_DIV: int = 4
    SYNC_ZC_LEVEL: float = 0.0
    TRIGGER: int = 0
    STOP_ON_TIME: int = 1
    COLLECT_TIME: float = 3000.0
    MODE: int = 1  # T2=0, T3=1

# --- Initialize SPC safely ---
def init_spc():
    global _initialized
    with _spc_lock:
        if _initialized:
            return
        with bh_spc.ini_file(
            bh_spc.minimal_spcm_ini(spcm.DLLOperationMode.HARDWARE)
        ) as ini:
            spcm.init(ini)
        _initialized = True

def set_parameters(params: SPCParams):
    with _spc_lock:
        for name, value in params.dict().items():
            spcm.set_parameter(_mod_no, getattr(spcm.ParID, name), value)

def read_microtimes(duration_s: float):
    with _spc_lock:
        spcm.start_measurement(_mod_no)
    start_time = time.monotonic()
    data = []

    try:
        while time.monotonic() - start_time < duration_s:
            buf = spcm.read_fifo_to_array(_mod_no, 32768)
            if len(buf):
                data.append(buf)
            if len(buf) < 32768:
                time.sleep(0.05)

        # Drain remaining
        while True:
            buf = spcm.read_fifo_to_array(_mod_no, 32768)
            if not len(buf):
                break
            data.append(buf)

    finally:
        with _spc_lock:
            spcm.stop_measurement(_mod_no)

    if not data:
        raise RuntimeError("No data collected.")

    records = np.concatenate(data).view(np.uint32)
    photons = np.extract(np.bitwise_and(records, 0b1001 << 28) == 0, records)
    micro = np.bitwise_and(np.right_shift(photons, 16), (1 << 12) - 1)
    micro = (1 << 12) - 1 - micro
    return micro

def build_histogram(microtimes, tac_range_ns=50.0, bins=64):
    times_ns = microtimes * (tac_range_ns / 4096)
    bin_edges = np.linspace(0.0, tac_range_ns, bins + 1)
    counts, _ = np.histogram(times_ns, bins=bin_edges)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    return bin_centers.tolist(), counts.tolist()

# --- API endpoints ---
@app.on_event("startup")
def startup_event():
    init_spc()
    print("SPC initialized and ready.")

@app.post("/set_parameters")
def api_set_parameters(params: SPCParams):
    try:
        set_parameters(params)
        return {"status": "Parameters set successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/set_parameter")
def api_set_parameter(param: dict):
    try:
        name = param["name"]
        value = param["value"]
        set_parameters({name: value})
        return {"status": f"{name} set to {value}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/measure")
def api_measure(params: SPCParams):
    try:
        set_parameters(params)
        micro = read_microtimes(params.COLLECT_TIME)
        bins, counts = build_histogram(micro, tac_range_ns=params.TAC_RANGE)
        return {"bin_centers": bins, "counts": counts}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/stop")
def api_stop():
    def stop_measurement():
        try:
            spcm.stop_measurement(_mod_no)
            return {"status": "Measurement stopped"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
