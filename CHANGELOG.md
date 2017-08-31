# Changelog

All notable changes to this project will be documented in this file.

## [v2.0.1] - 2017-08-31
### Added
**User interaction:**
- Added a loading-bar during curve-calculation to give user indication on current status of processing.

### Changed
**Curve Processing:**
- Rewrote NURBS and ellipse calculation to be quicker and use less resources.
- Disabled unnecessary updating of the screen, allowing for much faster processing times.


## [v2.0.0] - 2017-08-23
### Added
**Project:**
- Project now available on GitHub for ease of access to the latest file as well as having the ability to contribute for anyone who may want to.

**Layers:**
- Script will now recognise layers with whitespace.
- Script will not ask for cut or engrave layer if there is only one layer present in document named the default name of either cut or engrave. It will recognise the one, and not ask for the other.

**Curve processing:**
- Script will now check for duplicate geometry and give option to exit if any is found.
- Script will now check for non-planar geometry and  give option to exit if any is found.
- Script will check if planar curves are in the World XY plane and give option to exit if any is not.
- Arcs and circles are now calculated to use circular motion cut (G02 / G03).
- Rounding errors in circle-calculation will be made up for using a line at the end of the cut, making sure the entire circle is cut.
- Script pauses if objects are skipped or out-of-bounds and prompts user to exit or continue.

**Sorting:**
- When selecting an acrylic-profile, user will have the option to use an alternative sort, aiming to mitigate significant over-heating and warping of the material. 

**File system:**
- Script now checks if final file was successfully created before exiting.

**User interaction:**
- If script exits because of invalid geometry (non-planar, out of bounds++) program will exit and select the geometry in question.

### Changed
**Layers:**
- Re-wrote function for getting layer name. No longer need for two separate *get\_layer\_name* functions.

**Curve processing:**
- Ellipses and NURBS are still calculated by first reducing them to multiple lines first but has been rewritten to create better curvature.
- Rewritten code generation for polylines and polycurves to create better cuts.

**Sorting:**
- Rewrote sorting algorithm to use a depth-first, sorting by both parent-child relationships and sorts siblings by XY coordinates. This decreases unneeded criss-crossing in most cases while also prevents items from falling down before any remaining child object within have been cut.

**G-code output:**
- Final G-code will now only contain engrave or cutting code if there has been any objects in the respective layers. This to reduce unnecessary noise.
- Added comments explaining the various code-sections in the final G-code file, increasing G-code readability
- All G-code coordinates now use Decimal module for rounding instead of math.round for increased precision and control.

**Statistics:**
- Reworked time-estimate to also account for laser slew movement between cuts, allowing the estimated time to be near exact the duration of the file.


### Removed
