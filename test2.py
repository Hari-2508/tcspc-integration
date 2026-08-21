import ctypes
import time
from ctypes import c_short, c_int, c_ushort, POINTER, byref, c_char_p
from ctypes import cast

# Load DLL
dll_path = r"C:\Program Files (x86)\BH\SPCM\DLL\spcm64.dll"
spc = ctypes.WinDLL(dll_path)

# Constants - Adjust as needed
MAX_NO_OF_SPC = 2  # Example: max modules in system
SPC_ARMED = 1
SPC_OVERFL = 0x4000  # example overflow flag; verify exact value

# Structure for memory info (matches C struct)
class spc_mem_info(ctypes.Structure):
    _fields_ = [
        ("max_block_no", c_int),
        ("maxpage", c_int),
        ("block_length", c_int),
        ("blocks_per_frame", c_int),
        ("frames_per_page", c_int),
    ]

# Define ctypes function prototypes for used DLL functions
spc.SPC_enable_sequencer.argtypes = [c_int, c_short]
spc.SPC_enable_sequencer.restype = c_short

spc.SPC_set_parameter.argtypes = [c_int, c_int, c_int]
spc.SPC_set_parameter.restype = c_short

spc.SPC_configure_memory.argtypes = [c_int, c_short, c_short, POINTER(spc_mem_info)]
spc.SPC_configure_memory.restype = c_short

spc.SPC_fill_memory.argtypes = [c_int, c_int, c_int, c_int]
spc.SPC_fill_memory.restype = c_short

spc.SPC_set_page.argtypes = [c_int, c_int]
spc.SPC_set_page.restype = c_short

spc.SPC_clear_rates.argtypes = [c_int]
spc.SPC_clear_rates.restype = c_short

spc.SPC_get_sync_state.argtypes = [c_int, POINTER(c_short)]
spc.SPC_get_sync_state.restype = c_short

spc.SPC_start_measurement.argtypes = [c_int]
spc.SPC_start_measurement.restype = c_short

spc.SPC_test_state.argtypes = [c_int, POINTER(c_short)]
spc.SPC_test_state.restype = c_short

spc.SPC_get_time_from_start.argtypes = [c_int, POINTER(ctypes.c_float)]
spc.SPC_get_time_from_start.restype = c_short

spc.SPC_read_rates.argtypes = [c_int, POINTER(ctypes.c_int)]  # Simplified; adjust struct if needed
spc.SPC_read_rates.restype = c_short

spc.SPC_pause_measurement.argtypes = [c_int]
spc.SPC_pause_measurement.restype = c_short

spc.SPC_restart_measurement.argtypes = [c_int]
spc.SPC_restart_measurement.restype = c_short

spc.SPC_stop_measurement.argtypes = [c_int]
spc.SPC_stop_measurement.restype = c_short

spc.SPC_read_data_page.argtypes = [c_int, c_int, c_int, POINTER(c_ushort)]
spc.SPC_read_data_page.restype = c_short

spc.SPC_get_break_time.argtypes = [c_int, POINTER(ctypes.c_float)]
spc.SPC_get_break_time.restype = c_short

spc.SPC_save_data_to_sdtfile.argtypes = [c_int, POINTER(c_ushort), c_int, c_char_p]
spc.SPC_save_data_to_sdtfile.restype = c_short



def main():
    # Initialize and configure
    ret = spc.SPC_init(b"C:\\Program Files (x86)\\BH\\SPCM\\DLL\\spcm.ini")
    print("SPC_init returned:", ret)
    if ret != 0:
        print("SPC_init failed with code:", ret)
        return
    spc_dat_adc_resolution = 12  # example ADC resolution, replace as needed
    no_of_routing_bits = 0

    spc_mem = spc_mem_info()

    # For demo, assume both modules active
    mod_active = [True] * MAX_NO_OF_SPC
    no_of_active_spc = sum(mod_active)
    active_modules = [0]

    # Enable sequencer disabled (0)
    for mod_no in active_modules:
        ret = spc.SPC_enable_sequencer(mod_no, 0)
        print(f"SPC_enable_sequencer({mod_no}): {ret}")
        if ret != 0:
            print("Enable sequencer failed for module", mod_no)
            return

    # Configure memory
    ret = spc.SPC_configure_memory(mod_no, spc_dat_adc_resolution, no_of_routing_bits, byref(spc_mem))
    print("SPC_configure_memory returned:", ret)
    if ret != 0:
        print("Memory configuration failed", mod_no)
        return

    max_block_no = spc_mem.max_block_no
    max_page = spc_mem.maxpage
    max_curve = max_block_no // max_page
    block_length = spc_mem.block_length
    page_size = spc_mem.blocks_per_frame * spc_mem.frames_per_page * block_length

    # Create buffer for all active modules
    #BufferType = c_ushort * (page_size * no_of_active_spc)
    #buffer = BufferType()
    buffer = (c_ushort * page_size)()

    meas_page = 0
    offset_value = 0

    # Fill (clear) memory for all modules
    ret = spc.SPC_fill_memory(-1, -1, meas_page, offset_value)
    print("SPC_fill_memory returned:", ret)
    if ret < 0:
        print("Error during memory fill")
        return

    # Set measurement page
    for mod_no in active_modules:
        if mod_active[mod_no]:
            ret = spc.SPC_set_page(mod_no, meas_page)
            print(f"SPC_set_page({mod_no}, {meas_page}): {ret}")

    # Clear rates and get sync state
    sync_state = [c_short(0) for _ in active_modules]
    for mod_no in active_modules:
        if mod_active[mod_no]:
            spc.SPC_clear_rates(mod_no)
            spc.SPC_get_sync_state(mod_no, byref(sync_state[mod_no]))
            print(f"Module {mod_no} sync state: {sync_state[mod_no].value}")

    # Start measurement on all modules
    armed = True
    for mod_no in active_modules:
        if mod_active[mod_no]:
            ret = spc.SPC_start_measurement(mod_no)
            print(f"SPC_start_measurement({mod_no}): {ret}")
            if ret < 0:
                armed = False

    # Measurement loop - monitor all modules
    old_time = 0.0
    disp_time = 1.0
    collection_paused = [False] * MAX_NO_OF_SPC
    mod_state = [c_short(0) for _ in range(MAX_NO_OF_SPC)]

    while armed:
        spc_state = 0
        for mod_no in active_modules:
            if not mod_active[mod_no]:
                continue
            ret = spc.SPC_test_state(mod_no, byref(mod_state[mod_no]))
            spc_state |= mod_state[mod_no].value

        if spc_state & SPC_ARMED:
            # You can check time elapsed, rates, etc here if needed
            time.sleep(0.5)
        else:
            armed = False
            if spc_state & SPC_OVERFL:
                print("Overflow detected!")
                # Optionally get break time
                ovfl_time = ctypes.c_float()
                for mod_no in active_modules:
                    if mod_active[mod_no] and (mod_state[mod_no].value & SPC_OVERFL):
                        spc.SPC_get_break_time(mod_no, byref(ovfl_time))
                        print(f"Overflow break time on module {mod_no}: {ovfl_time.value}")
                        break

    # Read results for each active module
    ptr_offset = 0
    j = 0
    for mod_no in active_modules:
        if not mod_active[mod_no]:
            continue
        buf_ptr = ctypes.cast(ctypes.byref(buffer, ptr_offset * ctypes.sizeof(c_ushort)), POINTER(c_ushort))
        ret = spc.SPC_read_data_page(mod_no, meas_page, meas_page, buf_ptr)
        print(f"SPC_read_data_page({mod_no}) returned:", ret)
        if ret != 0:
            print(f"Failed to read data page from module {mod_no}")
            return
        j += 1
        ptr_offset += page_size
        if j == no_of_active_spc:
            break

    # Optional: save to .sdt file (if DLL function available)

    #filename = c_char_p(b"C:\\Users\\user\\Documents\\dll_results.sdt")
    #print("First few values:", list(buffer[:10]))
    #buffer_ptr = cast(buffer, POINTER(c_ushort))
    #ret = spc.SPC_save_data_to_sdtfile(-1, buffer_ptr, page_size, filename)
    #print("SPC_save_data_to_sdtfile returned:", ret)

    print("Measurement complete.")

if __name__ == "__main__":
    main()
