import socket
import time
import numpy as np
from spc_server import init_spc, read_microtimes, build_histogram #save_histogram_txt, set_parameter,  close_spc
import bh_spc
from bh_spc import spcm

def start_tcp_server(host='0.0.0.0', port=8000, mod_no=0):
    """TCP server for remote control of SPC with mode support."""

    init_spc()
    current_mode = 0  # default T2 histogram
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen(1)
    print(f"TCP server listening on {host}:{port}")
    conn, addr = s.accept()
    print(f"Connected by {addr}")

    while True:
        try:
            data = conn.recv(1024).decode().strip()
            if not data:
                continue
            print(f"Received: {data}")

            # Exit command
            if data.lower() == 'exit':
                conn.sendall(b"Server closing.\n")
                break

            # Set parameter command
            elif data.lower().startswith('set '):
                parts = data.split()
                if len(parts) != 3:
                    conn.sendall(b"Usage: set PARAM VALUE\n")
                    continue
                param, value = parts[1], parts[2]

                if param.upper() == "MODE":
                    try:
                        mode = int(value)
                        if mode not in (0, 1):
                            raise ValueError("Mode must be 0 (T2) or 1 (T3)")
                        current_mode = mode
                        conn.sendall(f"Mode set to {current_mode}\n".encode())
                    except Exception as e:
                        conn.sendall(f"Error: {e}\n".encode())
                    continue

                # Other parameters
                try:
                    set_parameter(mod_no, param.upper(), value)
                    conn.sendall(b"Parameter set.\n")
                except Exception as e:
                    conn.sendall(f"Error: {e}\n".encode())

            # Measurement command
            elif data.lower().startswith('measure'):
                parts = data.split()
                duration = float(parts[1]) if len(parts) > 1 else 1.0

                # Ensure mode is set before measurement
                try:
                    if current_mode == 0:
                        # T2 histogram mode
                        micro = read_microtimes(mod_no, duration)
                        bin_centers, counts = build_histogram(micro, tac_range_ns=50.0)
                        save_histogram_txt("histogram_tcp.txt", bin_centers, counts)
                        conn.sendall(b"T2 measurement done, histogram saved.\n")
                    else:
                        # T3 FIFO mode
                        # For T3, we just read microtimes and save raw microtime data
                        micro = read_microtimes(mod_no, duration)
                        np.savetxt("fifo_data_tcp.txt", micro, header="Microtime values", fmt="%d")
                        conn.sendall(b"T3 measurement done, microtime data saved.\n")
                except Exception as e:
                    conn.sendall(f"Measurement error: {e}\n".encode())

            else:
                conn.sendall(b"Unknown command.\n")

        except Exception as e:
            conn.sendall(f"Error: {e}\n".encode())

    conn.close()
    s.close()
    close_spc()


if __name__ == "__main__":
    start_tcp_server()
