import ctypes
import time
from ctypes import c_short, c_int, c_ushort, c_char_p, POINTER, byref

class spc_mem_info(ctypes.Structure):
    _fields_ = [
        ("max_block_no", c_int),
        ("maxpage", c_int),
        ("block_length", c_int),
        ("blocks_per_frame", c_int),
        ("frames_per_page", c_int),
    ]

# Load DLL
dll_path = r"C:\Program Files (x86)\BH\SPCM\DLL\spcm64.dll"
spc = ctypes.WinDLL(dll_path)

# Define function signatures
spc.SPC_init.argtypes = [c_char_p]
spc.SPC_init.restype = c_short

spc.SPC_close.argtypes = []
spc.SPC_close.restype = c_short

spc.SPC_enable_sequencer.argtypes = [c_int, c_int]
spc.SPC_enable_sequencer.restype = c_short

spc.SPC_set_parameter.argtypes = [c_int, c_int, c_int]
spc.SPC_set_parameter.restype = c_short

spc.SPC_configure_memory.argtypes = [c_int, c_int, c_int, POINTER(spc_mem_info)]
spc.SPC_configure_memory.restype = c_short

spc.SPC_fill_memory.argtypes = [c_int, c_int, c_int, c_int]
spc.SPC_fill_memory.restype = c_short

spc.SPC_set_page.argtypes = [c_int, c_int]
spc.SPC_set_page.restype = c_short

spc.SPC_start_measurement.argtypes = [c_int]
spc.SPC_start_measurement.restype = c_short

spc.SPC_test_state.argtypes = [c_int, POINTER(c_short)]
spc.SPC_test_state.restype = c_short

spc.SPC_read_data_page.argtypes = [c_int, c_int, c_int, POINTER(c_ushort)]
spc.SPC_read_data_page.restype = c_short

# Define struct

# Constants (replace with actual values from spcm_def.h if available)
MODE = 0
NORMAL = 0
SPC_ARMED = 1
CFD_LVL0 = 20
SYNC_LVL = 48
TAC_RANGE = 0x03
COLLECT_TIME = 0x40
STOP_ON_TIME = 0x42

def get_int_input(prompt, default):
    try:
        return int(input(f"{prompt} [{default}]: ") or default)
    except ValueError:
        return default

def main():
    print("Initializing SPC...")
    ret = spc.SPC_init(b"C:\\Program Files (x86)\\BH\\SPCM\\DLL\\spcm.ini")
    if ret != 0:
        print("SPC_init failed with code", ret)
        return

    # User input
    cfd = get_int_input("Enter CFD Level (CFD_LVL0)", 50)
    tac = get_int_input("Enter TAC Range", 4)
    sync = get_int_input("Enter Sync Level", 50)
    trig = get_int_input("Enter Trigger Level", 100)
    collect_time = get_int_input("Enter Collection Time (ms)", 1000)
    stop_time = get_int_input("Enter Stop On Time", 1000)

    spc.SPC_enable_sequencer(-1, 0)
    spc.SPC_set_parameter(-1, MODE, NORMAL)
    spc.SPC_set_parameter(-1, CFD_LVL0, cfd)
    spc.SPC_set_parameter(-1, SYNC_LVL, sync)
    spc.SPC_set_parameter(-1, TAC_RANGE, tac)
    spc.SPC_set_parameter(-1, COLLECT_TIME, collect_time)
    spc.SPC_set_parameter(-1, STOP_ON_TIME, stop_time)

    mem_info = spc_mem_info()
    spc.SPC_configure_memory(-1, 8, 0, ctypes.pointer(mem_info))
    spc.SPC_fill_memory(-1, -1, 0, 0)
    spc.SPC_set_page(-1, 0)

    ret = spc.SPC_start_measurement(-1)
    if ret != 0:
        print("SPC_start_measurement failed with code", ret)
        spc.SPC_close()
        return

    print("Measurement started...")

    # Wait for measurement to finish
    state = c_short()
    while True:
        spc.SPC_test_state(-1, byref(state))
        if not (state.value & SPC_ARMED):
            break
        time.sleep(0.5)

    # Read data
    page_size = mem_info.blocks_per_frame * mem_info.frames_per_page * mem_info.block_length
    buffer = (c_ushort * page_size)()
    spc.SPC_read_data_page(-1, 0, 0, buffer)

    print("Histogram Data (first 20 bins):")
    for i in range(20):
        print(f"{i}: {buffer[i]}")

    spc.SPC_close()
    print("Measurement complete.")

if __name__ == "__main__":
    main()
