AA30_Python
-----------

A small Python program to control the Rig Expert AA30 through its USB port. Controls include a number of frequency span presets as well as a manual entry mode. Plots include R, X, VSWR, and a "time-delay reflectometer" calculation. 

It is what it is. 

Requirements:
numpy
pyqt6
pyqtgraph
serial
serial_device2

Build a local environment with make_local.sh
Engage the environment (varies on Windows, MacOX and Linux)
run the program: 
    python src/re_aa30.py
or:
    RE (if setup.py was run correctly)

Last update 28 Dec 2023 pbm

