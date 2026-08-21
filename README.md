# TCSPC Control Software

Python-based control software for operating a Becker & Hickl SPC-130 TCSPC module. The project provides routines for instrument initialization, acquisition parameter configuration, measurement control, histogram retrieval, and remote communication between the acquisition computer and external control systems.

The software was developed as part of a master's thesis project involving time-correlated single-photon counting (TCSPC) measurements on semiconductor nanostructures.

## Features

* Communication with the Becker & Hickl SPC-130 TCSPC module
* Initialization and configuration of acquisition parameters
* Start and stop TCSPC measurements
* Monitoring of the measurement status
* Retrieval of photon-count histograms
* Saving and processing acquired histogram data
* TCP/HTTP-based remote communication
* Support for integration with external control systems such as Tango Controls

## System Architecture

The basic software structure is:

```text
SPC-130 Hardware
       ↕
Becker & Hickl Software Interface
       ↕
Python Control Application
       ↕
Network Communication Interface
       ↕
Remote Control / Tango Device Server
```

The SPC-130 hardware is connected to a Windows computer, where the Python control application communicates with the TCSPC module. Measurement commands and acquired histogram data can be exchanged with another computer through the network interface.

## Repository Structure

```text
tcspc/
│
├── main.py
├── spc_server.py
├── tcspc_tcp_server.py
├── spcm.ini
└── .gitignore
```

### Main files

**`main.py`**
Main program used for testing and controlling the TCSPC acquisition.

**`pybhspc.py`**
Python interface containing functions used to communicate with the Becker & Hickl TCSPC software interface.

**`spc.py`**
Contains SPC-130 initialization, parameter configuration, and measurement-related functions.

**`spc_server.py`**
Provides network-based access to the TCSPC control functions.

**`tcspc_tcp_server.py`**
Implements TCP communication for remote measurement control and data transfer.

**`spcm.ini`**
Configuration file containing parameters required for initialization of the SPC-130 module.

**`test.py` and `test2.py`**
Test scripts used during development and debugging of the TCSPC interface.

## Requirements

The software requires:

* Windows
* Python 3
* Becker & Hickl SPC-130 / SPC-130EM TCSPC module
* Becker & Hickl device drivers and software libraries
* Required Python packages for the SPC interface and network communication

Install the required Python dependencies using:

```bash
pip install -r requirements.txt
```

if a `requirements.txt` file is provided.

## Basic Usage

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
```

Move into the project directory:

```bash
cd YOUR_REPOSITORY
```

Make sure the Becker & Hickl drivers and required software libraries are installed and that the SPC-130 module is detected by the acquisition computer.

The acquisition can then be started using the appropriate Python control script, for example:

```bash
python main.py
```

or the network server can be started using:

```bash
python spc_server.py
```

depending on the required configuration.

## Measurement Workflow

A typical TCSPC measurement follows the sequence:

```text
Initialize SPC-130
        ↓
Load acquisition parameters
        ↓
Configure TCSPC module
        ↓
Start measurement
        ↓
Monitor acquisition state
        ↓
Read histogram
        ↓
Transfer / save data
```

The acquired histogram contains the photon counts as a function of arrival-time channel and can subsequently be used for fluorescence-decay or lifetime analysis.

## Remote Control

The project also supports remote operation of the TCSPC acquisition system.

In the implemented configuration, the Windows acquisition computer communicates with a Linux-based control computer over the network. Commands such as parameter updates and measurement requests are sent to the Windows control application, while the resulting TCSPC histogram is returned to the remote computer for further processing and storage.

This architecture allows the SPC-130 module to be incorporated into a larger automated experimental control environment.

## Notes

This repository contains research software developed for laboratory use. Hardware-specific configuration may need to be modified depending on:

* SPC module configuration
* installed Becker & Hickl software version
* detector configuration
* synchronization source
* network configuration
* acquisition parameters

The Becker & Hickl proprietary drivers and DLL files are **not included** in this repository and must be obtained through the appropriate Becker & Hickl software installation.

## Project Context

This software was developed for experimental work involving ultrafast optical spectroscopy and time-correlated single-photon counting of semiconductor quantum wells. The objective of the software integration was to provide programmable and remote access to the TCSPC acquisition hardware and allow its integration into an automated experimental control system.
