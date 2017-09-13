# Readme: gcode-script

A Python script (IronPython 2.7.5) converting curve geometry from Rhinocerous to G-code instructions for CO2 laser-cutting. This script aims to utilise the laser-cutter's full range of motion using G00, G01, G02 and G03 moves.

The previous script used only G00 and G01 commands, cutting any curved shape with only linear movements and caused jagged and disfigured edges when cutting curves at high speeds. 

Ellipses and NURBS/interpolated curves are reduced to lines for the time being due to their complexity of being represented by circular arcs.

This new script is based on script V1.0 written by Asbjorn Steinskog (IDI) and Pasi Aalto (AB)


## Usage

1. Download this script and unpack it.
1. Save gcode_script.py in a location you can easily find.
1. Open Rhino with your intended file.
1. Organise your file:
   1. Clean up unnecessary geometry.
   1. Make sure the curves are planar and not outside the maximum allowed working area (X1900mmY1000mm).
   1. Move cutting and engraving curves into separate layers. 
      1. The script will automatically look for layers named 'Cut', 'cut', 'Engrave', and 'engrave' and assign them as layers for cutting or engraving.
      1. If these names are not found, the script will ask for a layer to use.
1. Type 'RunPythonScript' in the Rhino command line and press enter.
1. Navigate to the gcode_script.py you downloaded and select it.
1. The script will now run:
   1. If 'Engrave' or 'engrave' layer is not found you will be asked to choose a layer for engraving.
   1. If 'Cut' or 'cut' layer is not found, you will be asked to choose a layer for cutting.
1. The script will now ask for which material profile to use, choose one.
1. The script will now process the curves. Depending on the file this may take some time (2 - 20 seconds).
1. After processing, the script will ask you for a location to save the file.
   1. The script automatically adds the material profile as a suffix to the name so that you know what material you chose.
1. A summary of the file will be shown. Please pay special attention to "Skipped objects" and "Skipped out of bounds objects".
1. Take note of the "Total estimated time to run this file". This is an approximation on how long this will take to perform by the laser-cutter.
1. Transfer the saved G-code file to the laser-cutter's dropbox folder.
1. Make sure you have booked a session on the laser-cutter before use.
1. Head down to the workshop, start the laser-cutter and run your file.


## MultiCam GCodes
These are the important G-codes that are being used in the current script. 

```
G00:     High speed move (slew)          //Used between cuts
G01:     Linear move (machine)           //Used when cutting linear
G02:     Clockwise rotation              //Used when cutting arcs
G03:     Counterclockwise rotation       //Used when cutting arcs
M12:     Start laser                     //Used at the beginning of the cut
M22:     Stop laser                      //Used at the end of the cut
```
Additionally there are some G-codes added to the start and end of the file providing the machine with startup and shutdown commands. These can be found from the script's material server. 

### Important note
This script is designed to work with a Chinese-brand C02 laser-cutter/engraver (unable to find exact brand and make) that uses a MultiCam firmware.

##Versioning

This project does not use sematic versioning as there is no API.
Current versioning format follows following logic:

    X.Y.Z
    X: Increment on major feature additions, or major overhauling.  
    Y: Increment on minor feature additions, rewrite or rework.
    Z: Increment on minor fixes and bugs.  
