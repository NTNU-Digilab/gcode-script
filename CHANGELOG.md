# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [v1.9-beta.1] - 2017-08-23
### Added
**Project:**
- Project now available on GitHub for ease of access to the latest file as well as having the ability to contribute for anyone who may want to.

**Layers:**
- Script will now recognise layers with whitespace.
- Script will not ask for cut or engrave layer if there is only one layer present in document named the default name of either cut or engrave. It will recognise the one, and not ask for the other.

**Curve processing:**
- Script now 
- Script will now check for duplicate geometry and exit if any is found.
- Script will now check for non-planar geometry and exit if any is found.
- Script will check if planar curves are in the World XY plane, exit if any is not.
- Arcs and circles are now calculated to use circular motion cut.
- Rounding errors in circle-calculation will be made up for using a line at the end of the cut, keeping sure the entire circle is cut.
- Script pauses if objects are skipped or out-of-bounds and prompts user to exit or continue.

**Sorting:**
- When selecting an acrylic-profile, user will have the option to use an alternative sort, hopefully mitigating over-heating and warping of the material.

**File system:**
- Script now checks if final file was successfully created before exiting.

### Changed
**Layers:**
- Re-wrote function for getting layer name. No longer need for two separate get_layer_name functions

**Curve processing:**
- Ellipses and NURBS are still calculated using multiple lines but has been rewritten to create better curvature.
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
