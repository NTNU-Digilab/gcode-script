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



## MultiCam GCodes
   G00:     High speed move (slew)          //Used between cuts
   G01:     Linear move (machine)           //Used when cutting
   G02:     Clockwise rotation              //Used when cutting
   G03:     Counterclockwise rotation       //Used when cutting
   M12:     Start laser                     //At the beginning of the cut
   M22:     Stop laser                      //At the end of the cut

### Important note
This script is designed to work with a chinese-brand C02 laser-cutter/engraver (unable to find exact brand and make) that uses a MultiCam firmware.
