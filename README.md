# gcode-script Readme

A python script (IronPython 2.7.5) converting curve geometry from Rhinocerous to G-code instructions for CO2 laser-cutting. This script aims to utilise the laser-cutter's full range of motion using G00, G01, G02 and G03 moves.

The previous script used only G00 and G01 commands, cutting any curved shape with only linear movements and caused jagged and disfigured edges when cutting curves at high speeds. 

Ellipses and NURBS/interpolated curves are reduced to lines for the time being due to their complexity of being represented by circular arcs.

This new script is based on script V1.0 written by Asbjorn Steinskog (IDI) and Pasi Aalto (AB)


    @date:           27.06.2017
    @author:         Andreas Weibye
    @organisation:   Norwegian University of Science and Technology
    @copyright:      MIT License
    @version:        1.95


## Usage

1. Download this script.
1. Save it in a location you can easily find.
1. Open Rhino and open your intended file.
1. Organize your file:
   1. Clean up uneccessary geometry.
   1. Make sure the curves are planar and not outside the maximum allowed working area (X1900mmY1000mm).
   1. Move cutting and engraving curves into separate layers.
      1. The script will automatically look for layers named 'Cut' and/or 'Engrave'.
      1. If these are not found, the script will ask for a layer to use.
   1. Type 'RunPythonScript' in the Rhino command line and press enter.
   1. Navigate to the gcode_script you downloaded and select.
   1. The script will now run:
      1. If 'Engrave' or 'engrave' layer is not found you will be asked to chooce a layer for engraving.
      1. If 'Cut' or 'cut' layer is not found, you will be asked to chooce a layer for cutting.
      1. The script will now ask for which material profile to use, chooce one.
      1. The script will now process the curves. Depending on the file this may take some time (2 - 20 sec).
      1. After processing, the script will ask you for a location to save the file.
        1. The script automatically adds the material profile as a suffix to the name so that you know what material you chose.
      1. A summary of the file will be shown. Please pay special attention to "Skipped objects" and "Skipped out of bounds objects".
      1. Take note of the "Total estimated time to run this file". This is an approximation on how long this will take to perform by the laser-cutter.

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
This script is designed to work with a chinese-brand C02 laser-cutter/engraver (unable to find exact brand and make) that uses a MultiCam firmware.
