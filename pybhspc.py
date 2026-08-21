import bh_spc
from bh_spc import spcm
import numpy as np
import matplotlib.pyplot as plt
import time


def prompt_parameters():
    print("Enter measurement parameters or press Enter to use defaults:")

    def get_input(prompt, default, cast):
        try:
            val = input(f"{prompt} [{default}]: ")
            return cast(val) if val else default
        except Exception:
            return default

    return {
        'CFD_LIMIT_LOW': get_input("CFD Limit Low (mV)", 0.0, float),
        'CFD_LIMIT_HIGH': get_input("CFD Limit High (mV)", 80.0, float),
        'CFD_HOLDOFF': get_input("CFD Holdoff (ns)", 5.0, float),
        'CFD_ZC_LEVEL': get_input("CFD ZC Level", 0.0, float),

        'TAC_RANGE': get_input("TAC Range (ns)", 50.0, float),
        'TAC_LIMIT_LOW': get_input("TAC Limit Low (%)", 10.0, float),
        'TAC_LIMIT_HIGH': get_input("TAC Limit High (%)", 80.0, float),
        'TAC_GAIN': get_input("TAC Gain", 1, int),
        'TAC_OFFSET': get_input("TAC Offset (%)", 0.0, float),

        'SYNC_THRESHOLD': get_input("Sync Threshold (mV)", -20.0, float),
        'SYNC_HOLDOFF': get_input("Sync Holdoff (ns)", 4.0, float),
        'SYNC_FREQ_DIV': get_input("Sync Freq Div", 4, int),
        'SYNC_ZC_LEVEL': get_input("Sync ZC Level", 0.0, float),

        'TRIGGER': get_input("Trigger (0=SW, 1=EXT)", 0, int),
        'STOP_ON_TIME': 1,
        'COLLECT_TIME': get_input("Collection Time (s)", 0.01, float),

        'MODE': get_input("Mode (0=T2, 1=T3)", 1, int)
    }


def set_parameters(mod_no, params):
    for name, value in params.items():
        spcm.set_parameter(mod_no, getattr(spcm.ParID, name), value)


def read_and_process_data(mod_no, duration=0.1, buf_size=32768):
    spcm.start_measurement(mod_no)
    start_time = time.monotonic()
    data = []

    while True:
        if time.monotonic() - start_time >= duration:
            spcm.stop_measurement(mod_no)
            break
        buf = spcm.read_fifo_to_array(mod_no, buf_size)
        if len(buf):
            data.append(buf)
        if len(buf) < buf_size:
            time.sleep(0.001)

    while True:
        buf = spcm.read_fifo_to_array(mod_no, buf_size)
        if not len(buf):
            break
        data.append(buf)

    if not data:
        raise RuntimeError("No data collected.")

    records = np.concatenate(data).view(np.uint32)
    photons = np.extract(np.bitwise_and(records, 0b1001 << 28) == 0, records)
    microtimes = np.bitwise_and(np.right_shift(photons, 16), (1 << 12) - 1)
    microtimes = (1 << 12) - 1 - microtimes
    return microtimes


def process_and_display_decay(microtimes, tac_range_ns=50.0, bins=64):

    times_ns = microtimes * (tac_range_ns / 4096)

    # Compute histogram
    bin_edges = np.linspace(0, tac_range_ns, bins + 1)
    counts, _ = np.histogram(times_ns, bins=bin_edges)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # Print raw histogram data (counts per bin)
    print("\nRaw Histogram Data (bin counts):")
    print(counts.tolist())

    # Print decay curve values (time in ns vs counts)
    print("\nDecay Curve (time [ns] vs counts):")
    for t, c in zip(bin_centers, counts):
        print(f"{t:.3f} ns : {c} counts")

    np.savetxt("histogram_data.txt",
               np.column_stack((bin_centers, counts)),
               header="Time (ns)\tCounts", fmt="%.6f\t%d")
    print("\nHistogram data saved to histogram_data.txt")

    # Plot decay curve
    plt.plot(bin_centers, counts, drawstyle='steps-mid')
    plt.xlabel("Time (ns)")
    plt.ylabel("Photon Counts")
    plt.title("Fluorescence Decay Curve")
    plt.grid(True)
    plt.show()

#def plot_decay_curve(microtimes, tac_range_ns=50.0, bins=64):
    #bin_edges = np.linspace(0, tac_range_ns, bins + 1)  # Bin edges in ns
    #counts, _ = np.histogram(microtimes * (tac_range_ns / 4096), bins=bin_edges)

    #bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    #plt.plot(bin_centers, counts, drawstyle='steps-mid')
    #plt.xlabel("Time (ns)")
    #plt.ylabel("Photon Counts")
    #plt.title("Fluorescence Decay Curve")
    #plt.grid(True)
    #plt.show()


def main():
    with bh_spc.ini_file(
            bh_spc.minimal_spcm_ini(spcm.DLLOperationMode.HARDWARE)) as ini:
        spcm.init(ini)
        mod_no = 0

        params = prompt_parameters()
        set_parameters(mod_no, params)
        print("\nRunning measurement...")
        microtimes = read_and_process_data(mod_no, duration=params['COLLECT_TIME'])
        print("\n--- Raw Microtime Data (First 100 values) ---")
        print(microtimes[:100])
        print(f"\nTotal microtime records collected: {len(microtimes)}")
        process_and_display_decay(microtimes, tac_range_ns=50.0)
        #plot_decay_curve(microtimes, tac_range_ns=50.0)


if __name__ == "__main__":
    main()
