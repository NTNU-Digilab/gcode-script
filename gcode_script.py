# coding: utf8

'''

    @date:           27.06.2017
    @author:         Andreas Weibye
    @organisation:   Norwegian University of Science and Technology
    @copyright:      MIT License
    @version:        1.95

    @summary: Converts Rhino curves into gcode for the CO2 plasma laser.
              This script aims to utilise the laser-cutter's full range of
              motion using G00, G01, G02 and G03 moves.

    MultiCam GCodes
    G00:     High speed move (slew)          //Used between cuts
    G01:     Linear move (machine)           //Used when cutting
    G02:     Clockwise rotation              //Used when cutting
    G03:     Counterclockwise rotation       //Used when cutting
    M12:     Start laser                     //At the beginning of the cut
    M22:     Stop laser                      //At the end of the cut

    The previous script used only G00 and G01 commands, cutting any curved
    shape with only linear movements and caused jagged and disfigured
    edges when cutting curves at high speeds.

    Ellipses and NURBS/interpolated curves are reduced to lines for the time being
    due to their complexity of being represented by circular arcs.

    Based on script V1.0 written by Asbjorn Steinskog (IDI) and Pasi Aalto (AB)


    @Changelog: 1.95

    Layers:
    * Script will now recognise layers with whitespace.
    * Script will not ask for cut or engrave layer if there is only one layer
      present in document named the default name of either cut or engrave. It
      will recognise the one, and not ask for the other.
    * Re-wrote function for getting layer name. No longer need for two separate
      get_layer_name functions 

    Curve processing:
    * Script will now check for duplicates and exit if any is found.
    * Arcs and circles are now calculated to use circular motion cut.
    * Rounding errors in circle-calulation will be made up for using a line,
      keeping sure the entire circle is cut.
    * Ellipses and NURBS are still calculated using multiple lines.
    * Script pauses if objects are skipped or out-of-bounds and prompts
      user to exit or continue.
    * Polylines and polycurves will no longer start and stop between each
      sub-curve, resulting in better cuts.

    Sorting:
    * Reworked sorting to use a depth-first algorithm sorting by both parent-child
      relationships and sorts siblings by XY coordinates, drastically decreasing
      unneeded criss-crossing between cuts while still preventing items to fall
      down from the laser-bed before being completed.
    * When selecting an acrylic-profile, user will have option to use an alternative
      sort, hopefully mitigating overheating and warping of the material.

    Gcode output:
    * Final gcode will now only contain engrave or cutting code if there has
      been any objects in the respective layers.
    * Added comments explaining code-sections in the final gcode file.
    * All gcode coordinates now use Decimal module for rounding instead of
      math.round for increased precision and control.

    Statistics:
    * Reworked time estimate to also account for laser movement between cuts,
      allowing the estimated time to be near exact the duration of the file.

    File system:
    * Script now checks if final file was successfully created before exiting.

    @Known_bugs_and_things_to_fix:
    * Script throws an error if layers have special characters in their name (ÆØÅ).
      This needs to be fixed.
    * Curves and ellipses need to be divided depending on their curvature. Too high curvature
      makes way too many divisions, leading to bad cuts.
    * Need to add check if curves are flat and within bounds when fetching from layers.
    * Need to clean up uneccesary code from script
    * Add a box telling people that their laser-file is wasteful
        (calculate 'spread' of items, see how much wasted space in between)
    * Curves will be flipped to always have start of curve closer to origin
      than end of curve. This will reduce unecessary criss-crossing and
      improve cut-times.
'''

#===============================================================================
# IMPORTS
#===============================================================================
import datetime
from decimal import Decimal, Context, getcontext, ROUND_HALF_DOWN
import math
import os
import time
import urllib

import json as j
import rhinoscriptsyntax as rs
from rhinoscript.curve import CurveDomain


#===============================================================================
# GLOBAL VARIABLES
#===============================================================================
_CUTTING_LAYER_DEFAULT_NAME = 'cut'  # Lower case name to be used for cut_layer
_ENGRAVING_LAYER_DEFAULT_NAME = 'engrave'  # Lower case name to be used for engrave_layer
_CURVE_TO_LINE_SEGMENT_LENGTH = 0.7
_G00_SPEED = 45 # The speed of slew movements
_ESTIMATE_MODIFIER = 1 # Optional factor to multiply speed estimate with to compensate for acceleration


# URL = 'http://www.ntnu.no/ab/digilab/Web/laser3.json' # Server containing acryllic material settings
URL = 'http://www.ntnu.no/ab/digilab/Web/laser.json' # Server containing regular material settings
SCRIPT_VERSION = 1.95

WORLD_X_VECTOR = rs.VectorCreate(([1.0, 0.0, 0.0]), ([0.0, 0.0, 0.0]))

BOUNDS_MAX_X = 0
BOUNDS_MAX_Y = 0

CONTEXT = Context(prec=28, rounding=ROUND_HALF_DOWN)
ROUNDING = Decimal('1.000')


class CurveObject:
    '''
    CurveObject is the basic object containing the curves
    and their meta data in this script.
    Parameters:
        guid(guid) : Unique identifier for the curve object from Rhino
        curve_type (string): 
        area (float): Area of object if curve is closed
        start_point (array): Start point of curve
        end_point (array): End point of curve
        center_point (array): Center point of curve if closed
        bounding_box (list): Extremes of the curves bounding box
                                [min_x, max_x, min_y, max_y]
    Returns:
        CurveObject (CurveObject): Returns self after creation.
    '''

    def __init__(self, guid, curve_type, curve_closed,
                 curve_area, start_point, end_point,
                 center_point, bounding_box,):

        self.guid = guid
        self.curve_type = curve_type
        self.closed = curve_closed
        self.area = curve_area
        self.start_point = start_point
        self.end_point = end_point
        self.center_point = center_point
        self.bounding_box = bounding_box


def get_from_url(URL):
    '''
    Getting data from server in json format.
    Parameters:
        URL (string): URL containing the server
    Returns:
        data (json.data): Material data if successful
        False: If unable to get data
    '''

    print('Getting settings from server')

    try:
        json_data = urllib.urlopen(URL)
    except:
        rs.MessageBox(
            'Unable to connect to online settings server.\nYou or the server may be offline.\n'
            'Please check your internet connection',
            0 | 48, 'Error: Unable to connect')
        return False

    try:
        data = j.load(json_data)
    except:
        rs.MessageBox('Connected to server but no data found.', 0 | 48, 'Error: No data found')
        return False

    json_data.close()
    return data


def list_materials(server_data, title='Choose material'):
    '''
    Lists materials from server in the UI and prompts the user to chose one.
    Parameters:
        data (json.data): Material data
    Returns:
        material_index (int): Returns the material_index of the chosen material
    '''

    print('Generating material list from server')

    material_index = 0
    items = []

    for i in range(len(server_data['Materials'])):
        items.append(server_data['Materials'][i]['MaterialName'])

    material = rs.GetString(title, None, items)

    for i in range(len(server_data['Materials'])):
        if material == server_data['Materials'][i]['MaterialName']:
            material_index = i
        elif material is None:
            return None

    return material_index


def approve_unit_system():
    '''
    Making sure the Rhino document is currently working in millimetres
    as that is the only system the laser understands.
    Parameters:
        None
    Return:
        True: If units set to millimetres
        False: If unable to set to millimetres

    Note:
        UnitSystem explained:
            2 - Millimetres (1.0e-3 meters)
            3 - Centimetres (1.0e-2 meters)
            4 - Meters
            5 - Kilometres (1.0e+3 meters)
            6 - Microinches (2.54e-8 meters, 1.0e-6 inches)
            7 - Mils (2.54e-5 meters, 0.001 inches)
            8 - Inches (0.0254 meters)
            9 - Feet (0.3408 meters, 12 inches)
            10 - Miles (1609.344 meters, 5280 feet)
    '''

    print('Checking system units')

    if rs.UnitSystem() != 2:
        unit_system = rs.MessageBox(
            'The document\'s unit system has to be set to millimetres because '
            'that is the only thing the laser knows how to read. \n\nThis can be '
            'done with auto-scaling (if you have designed with other units) or by '
            'converting only (if everything is meant to be in mm, but the units are '
            'just wrong)\n\nDo you wish to auto-scale everything in the conversion process?',
            buttons=3, title='Error: Document has wrong units')

        if unit_system == 6:
            rs.UnitSystem(2, True)
            print('Unit system set to millimetres with auto-scaling.')
            return True

        elif unit_system == 7:
            rs.UnitSystem(2, False)
            print('Unit system set to millimetres with auto-scaling.')
            return True

        else:
            return False
    return True

def get_layer_name(layer_name):
    '''
    Will look for any layer in document named layer_name.
    If not found in document, prompt user for layer to be used.
    Parameters:
        layer_name (string) : layer name to look for
    Returns:
        cut_layer (Rhino.layer) : Layer object to be used for cutting
        None: If not able to find a layer
    '''
    if layer_name == _ENGRAVING_LAYER_DEFAULT_NAME:
        layer_name_present_participle = 'engraving'
    
    if layer_name == _CUTTING_LAYER_DEFAULT_NAME:
        layer_name_present_participle = 'cutting'

    print('Getting %s layer' % layer_name_present_participle)

    layer_found = False
    document_layers = rs.LayerNames()
    fixed_string_layers = []

    # If there is only one layer present in the document, check for
    # any default name then continue if found.
    if len(document_layers) == 1:
        if layer_name == _CUTTING_LAYER_DEFAULT_NAME:
            if document_layers[0].lower() == _CUTTING_LAYER_DEFAULT_NAME.lower():
                return document_layers[0]
            elif document_layers[0].lower() == _ENGRAVING_LAYER_DEFAULT_NAME.lower():
                return None

        if layer_name == _ENGRAVING_LAYER_DEFAULT_NAME:
            if len(document_layers) == 1:
                if document_layers[0].lower() == _CUTTING_LAYER_DEFAULT_NAME.lower():
                    return None
                elif document_layers[0].lower() == _ENGRAVING_LAYER_DEFAULT_NAME.lower():
                    return document_layers[0]

    if document_layers:
        for layer in document_layers:
            if layer.lower() == layer_name.lower():
                layer_found = True
                print('Found %s layer to be used: ' % layer_name_present_participle + str(layer))
                return layer
            # Rhino is unable to have list items containing whitespace as a selectable
            # UI element. To solve this, replacing whitespace with underscore.
            # TODO: Apply fix for special characters in string here
            layer = layer.replace(' ', '_')
            fixed_string_layers.append(layer)

        if not layer_found:
            fixed_string_layers.append('None')  # Adding none as an option in the listing of layers
            lookup_layer = rs.GetString('Choose layer to be used for %s' % layer_name_present_participle, None, fixed_string_layers)
            if lookup_layer == 'None':
                print('No %s layer chosen' % layer_name_present_participle)
                return None
            elif lookup_layer not in document_layers:
                # If the layer name was altered by replacing whitespace with underscore,
                # revert back to the old name to be used for further processing.
                index = fixed_string_layers.index(lookup_layer)
                try:
                    lookup_layer = document_layers[index]
                except:
                    return None
            elif lookup_layer == False:
                print('No %s layer chosen' % layer_name_present_participle)
                return None
            return lookup_layer
    else:
        print('Error: No layers in document')
        return None


def get_objects_from_layer(layer_name):
    '''
    Getting every objects from specified layer.
    Parameters:
        layer_name (Rhino.layer) : Layer to get objects from
    Returns:
        curve_object_list (list) : List of Rhino.curve objects from layer
        None : if no objects on layer or no name given
    '''

    non_planar = []
    curve_object_list = []

    if layer_name is None:
        return None
    print('Getting objects from layer: ' + str(layer_name))
    # TODO: Add check if geometry is in same plane
    # TODO: Check bounding box against outer dimension of work area,
    #       prompt user to either fix or continue
        # TODO: If user backs out, select and highlight the affected geometry
        # and then proceed to create the bounding box in a new layer
    
    # Checking for duplicate objects in document
    rs.Command('SelDup', echo=False)
    duplicates = rs.SelectedObjects(include_lights=False, include_grips=False)
    if duplicates:
        response = rs.MessageBox(
            'Duplicate objects found in document.\n'
            + 'Exit script and remove duplicates?',
            4 | 48,
            'Duplicates found')
        if response == 6:
            return False
    
    # Fetching objects
    objects = rs.ObjectsByLayer(layer_name, False)
    if not objects:
        rs.MessageBox('Layer has no objects: ' + str(layer_name), 0, 'Error')
        return None

    # Extract only curve objects from objects in layer
    for obj in objects:
        if rs.IsCurve(obj):
            if rs.IsCurvePlanar(obj) == False:
                non_planar.append(obj)
            else:
                curve_object_list.append(obj)

    if len(non_planar) > 0:
        response = rs.MessageBox(
            '%s curves in document is not planar.\n' % str(non_planar)
            + 'Exit script and fix curves?',
            4 | 48,
            'Curves not planar')
        if response == 6:
            rs.UnselectAllObjects()
            rs.SelectObjects(non_planar)
            return False

    return curve_object_list


def interpret_curves(object_guid):
    '''
    Parsing and interpreting Rhino.curves into CurveObjects and adding
    meta data
    Parameters:
        object_guid (list) : List of Rhino.object guid to process
    Returns:
        curve_object_list (list): List of resulting CurveObjects
        objects_out_of_bounds (int): Number of objects out of bounds
        objects_skipped (int): Number of objects skipped
    '''

    print('Interpreting curves')

    # Variables
    objects_out_of_bounds = 0
    objects_skipped = 0
    curve_object_list = []

    if object_guid:

        for obj in object_guid:
            c_object = None
            curve_closed = None
            curve_type = ''
            curve_area = None

            # Check for curve validity
            if bounding_box(obj):
                # Get bounding box of objects
                curveBBminX, curveBBmaxX, curveBBminY, curveBBmaxY = bounding_box(obj)
                curve_bounding_box = [curveBBminX, curveBBmaxX, curveBBminY, curveBBmaxY]
                valid = True
            else:
                # Object is out of bounds.
                objects_out_of_bounds += 1
                valid = False

            if valid:
                # Check if curve is planar
                if not rs.IsCurvePlanar(obj):
                    valid = False
                    objects_skipped += 1

            if valid:
                # Check for open or closed curves
                if rs.IsCurveClosed(obj):
                    curve_closed = True
                else:
                    # If not closed, check if it makes sense to close it
                    if rs.IsCurveClosable(obj):
                        # If yes, then close it and assign the new object to the variable
                        obj = rs.CloseCurve(obj)
                        curve_closed = True
                    else:
                        curve_closed = False

                # Determine the type of curve
                if rs.IsCircle(obj):
                    curve_type = 'circle'
                    center_point = rs.CircleCenterPoint(obj)
                elif rs.IsArc(obj):
                    curve_type = 'arc'
                    center_point = rs.ArcCenterPoint(obj)
                elif rs.IsEllipse(obj):
                    curve_type = 'ellipse'
                    center_point = rs.EllipseCenterPoint(obj)
                elif rs.IsPolyCurve(obj):
                    curve_type = 'polycurve'
                    center_point = None
                elif rs.IsLine(obj):
                    curve_type = 'line'
                    center_point = None
                elif rs.IsPolyline(obj):
                    curve_type = 'polyline'
                    center_point = None
                else:
                    curve_type = 'curve'
                    center_point = None

                # Calculate closed curve area
                if curve_closed:
                    curve_area = rs.CurveArea(obj)[0]
                else:
                    curve_area = None

                # Get start and end point
                start_point = rs.CurveStartPoint(obj)
                end_point = rs.CurveEndPoint(obj)

                # Create a new curveObject containing the information generated
                c_object = CurveObject(obj, curve_type, curve_closed, curve_area, start_point,
                                      end_point, center_point, curve_bounding_box)

                curve_object_list.append(c_object)

        # Returning the list of interpreted objects, unsorted
        return curve_object_list, objects_out_of_bounds, objects_skipped
    else:
        return None


def sort_advanced(object_list, material_data=None):
    '''
    Sorting list depth-first with siblings sorted by XY coordinates.
    Parameters:
        object_list (list): List of CurveObjects to sort
    Returning:
        discovered_complete (list): List of CurveObjects, sorted
    '''

    curves_open = []
    curves_closed = []
    alternative_sort = False
    
    if material_data is not None:
        if 'Akryl' in str(material_data['MaterialName']):
            response = rs.MessageBox('Due to excessive heating when cutting acrylic, alternative '
                          + 'sorting method should be considered to spread out cuts more '
                          + 'evenly. This will lead to better cuts, but take longer time '
                          + 'to complete.\n\nUse alternative sorting?',
                          4 | 0, 'Acrylic material profile selected')
            if response == 6:
                alternative_sort = True


    # Splitting open and closed curves to get largest closed curves first
    # in list then pass the list to the recursive depth-first sort. 
    for entry in object_list:
        if entry.closed == True:
            curves_closed.append(entry)
        else:
            curves_open.append(entry)

    # Sort by area, then X, then Y, smallest first
    # Sort on secondary key
    curves_closed = sorted(
        curves_closed,
        key=lambda CurveObject: (CurveObject.start_point[0], CurveObject.start_point[1]),
        reverse=True
        )

    # Sort on primary key
    curves_closed = sorted(
        curves_closed,
        key=lambda CurveObject: CurveObject.area,
        reverse=True
        )

    if alternative_sort == False:
        # Sort open by start_point X and Y, lowest first
        curves_open = sorted(
            curves_open,
            key=lambda CurveObject: (CurveObject.start_point[0], CurveObject.start_point[1]),
            reverse=True
            )


    elif alternative_sort == True:
        #Alternative sort for heat mitigation when cutting acrylic.
        # Currently this cuts every nth (list_range) curve then repeats
        curves_open = sorted(
            curves_open,
            key=lambda CurveObject: (CurveObject.start_point[0], CurveObject.start_point[1]),
            reverse=True
            )
        list_range = 5
        split_list = [curves_open[i::list_range] for i in xrange(list_range)]
        curves_open_new = []
        for x in split_list:
            for y in x:
                curves_open_new.append(y)
        curves_open = curves_open_new


    # Combine open and closed again
    complete_list = curves_closed + curves_open
    discovered_complete = []

    # Depth first search for any items in complete_list
    while len(complete_list) > 0:
        discovered = []
        sort_depth_first(complete_list, complete_list[0], discovered)
        for x in discovered:
            complete_list.remove(x)
        discovered_complete += discovered

    # Reverse sorted list to get smallest items first
    discovered_complete.reverse()

    return discovered_complete


def sort_depth_first(complete_graph, current_vertex, discovered_list):
    '''
    Recursive depth-first sort
    Parameters:
        complete_graph (list): List of all nodes in graph
        current_vertex (CurveObject): Current node 
        discovered_list (list): List of items discovered
    '''

    # Add current vertex to discovered
    discovered_list.append(current_vertex)

    #Find children of current vertex
    children = findChildrenObjects(current_vertex, complete_graph)

    #If children not already discovered, call function recursively
    if children:
        for child in children:
            if child not in discovered_list:
                sort_depth_first(complete_graph, child, discovered_list)


def findChildrenObjects(parent, candidateList):
    '''
    Returning list of children of parent object from list of candidates.

    Parameters:
        parent (CurveObject): CurveObject to check for children
        candidateList (list): List of candidates to evaluate
    Returns:
        children (list): list of children CurveObjects
        None: if no children found or parent unable to contain childs
    '''

    children = []

    if parent.closed == True:
        for cand in candidateList:
            if parent.guid == cand.guid:
                # Do nothing, they are the same object
                pass
            elif cand.closed == True:
                result = rs.PlanarClosedCurveContainment(parent.guid, cand.guid)
                if result == 3: # Closed child is inside closed parent
                    children.append(cand)
            elif cand.closed != True:
                # Check if child bounding box is inside parent bounding box.
                # TODO: Add more checks for overlapping and edge-case scenarios.
                # Bounding_box: min_x, max_x, min_y, max_y
                if (cand.bounding_box[0] > parent.bounding_box[0] and
                    cand.bounding_box[1] < parent.bounding_box[1] and
                    cand.bounding_box[2] > parent.bounding_box[2] and
                    cand.bounding_box[3] < parent.bounding_box[3]):
                    #Open child is inside closed parent
                    children.append(cand)
        return children
    else:
        #Parent is open curve. It cannot have children
        return None


def bounding_box(object_guid):
    '''
    Returns the extremities of the bounding box for an object.

    Parameters:
        object (guid) : Object ID
    Returns:
        minX :      Minimum X value
        maxX :      Maximum X value
        minY :      Minimum Y value
        maxY :      Maximum Y value
        False: if any part of the object is outside the max allowable area
    '''

    if object_guid:
        bounding_box = rs.BoundingBox(object_guid)
        x_coordinate = [bounding_box[i][0] for i in range(len(bounding_box))]
        y_coordinate = [bounding_box[i][1] for i in range(len(bounding_box))]

        if (min(x_coordinate) < 0 or max(x_coordinate) > BOUNDS_MAX_X
                or min(y_coordinate) < 0 or max(y_coordinate) > BOUNDS_MAX_Y):
            return False

        return min(x_coordinate), max(x_coordinate), min(y_coordinate), max(y_coordinate)


def arc_calc(obj):
    '''
    Calculates direction of curve and offset values for a given arc or circle.
    Parameters:
        obj (guid): objectGUID of the curve to calculate
    Returns:
        gcode_direction (string): Returning G02 or G03 depending on clockwise or counterclockwise
        x_offset (Decimal): How long to offset in x-direction
        y_offset (Decimal): How long to offset in y-direction
    '''

    context = getcontext()
    # Setting decimal precision
    context.prec = 28

    # Circle/Arc direction
    gcode_direction = ''

    # Getting centre points
    if rs.IsArc(obj) and not rs.IsCircle(obj):
        center_point = rs.ArcCenterPoint(obj)
    elif not rs.IsArc(obj) and rs.IsCircle(obj):
        center_point = rs.CircleCenterPoint(obj)

    offset_vector = rs.VectorCreate(rs.CurveStartPoint(obj), center_point)
    offset_length = Decimal(rs.VectorLength(offset_vector))

    # Create midpoint on curve to evaluate directionality of curve
    if rs.IsCircle(obj):
        mid_point = rs.DivideCurve(obj, 4)

    elif rs.IsArc(obj):
        mid_point = rs.DivideCurve(obj, 2)

    # Create vector and cross-product
    mid_vector = rs.VectorCreate(mid_point[1], center_point)
    mid_vector_cross_product = Decimal(rs.VectorCrossProduct(offset_vector, mid_vector)[2])

    # Getting rid of -0.00 situations
    try:
        mid_vector_cross_product = context.divide(
            context.abs(mid_vector_cross_product),
            mid_vector_cross_product
            )
    except:
        # Tried 0/0: We need either +1 or -1 as a result
        # 0/0 should then be counted as +1
        mid_vector_cross_product = Decimal('1')

    # If the angle between start and end point has negative cross_productuct,
    # then use G03 (counterclockwise movement).
    # Else use the G02 clockwise movement
    if mid_vector_cross_product > 0:
        gcode_direction = 'G03'
    else :
        gcode_direction = 'G02'

    # Calculate angle in degrees between offset and worldX and get the cross product.
    offset_angle = Decimal(rs.VectorAngle(offset_vector, WORLD_X_VECTOR))
    # Get Z component from cross_productVector
    cross_product = Decimal(rs.VectorCrossProduct(offset_vector, WORLD_X_VECTOR)[2])

    try:  # Getting rid of -0.00 situations
        cross_product = context.divide(
            context.abs(cross_product),
            cross_product
            )
    except:
        # Tried 0/0: We need either +1 or -1 as a result
        # 0/0 will then be counted as +1
        cross_product = 1

    # The initial angle will always be 0<angle<180 thus we must use the cross-product
    # to increase this to a full 360 circle.
    if cross_product < 0:
        offset_angle = 360 - offset_angle

    #===========================================================================
    # Calculating offset X and Y components
    # WARNING THIS HAS ISSUES WITH FLOATING POINT ARITHMETICS
    # Floating point arithmetic causes things like Cos(0deg) = 0.000000003245312
    # which is NOT EQUAL 0
    #===========================================================================
    cos = Decimal(math.cos(math.radians(offset_angle)))
    sin = Decimal(math.sin(math.radians(offset_angle)))
    # Workaround for some floating point arithmetic issues
    if sin == 1.00 or sin == -1.00:
        cos = 0.00
    if cos == 1.00 or cos == -1.00:
        sin = 0.00

    # Calculate offset magnitude in X and Y. Reverse X to get correct movement
    x_offset = Decimal(cos) * Decimal(offset_length) * Decimal('-1')
    y_offset = Decimal(sin) * Decimal(offset_length)

    return gcode_direction, x_offset, y_offset


def draw_arc(center_point, vector_1, vector_2):
    '''
    Draws an arc on the document from a center point, start vector and end vector
    using vector_1.length as radius. This function is used for the calculation of ellipses.
    Parameters:
        center_point: Point for the arc to be drawn from
        vector1: The direction of the start edge, and the length of the radius
        vector2: The angle to end the arc
    Returns:
        arc: rs.Arc object created
    '''
    vector_1_Len = rs.VectorLength(vector_1)

    angle_degree = rs.VectorAngle(vector_1, vector_2)

    # Creating plane to define start location and angle of arc
    plane = rs.WorldXYPlane()
    plane = rs.MovePlane(plane, center_point)
    plane_angle = rs.VectorAngle([1, 0, 0], vector_1)
    plane_cross_product = rs.VectorCrossProduct([1, 0, 0], vector_1)[2]
    if plane_cross_product < 0:
        plane_angle = 360 - plane_angle
    # Rotating plane around the Z-axis
    plane = rs.RotatePlane(plane, plane_angle, [0, 0, 1])
    # Drawing the arc
    arc = rs.AddArc(plane, vector_1_Len, angle_degree)

    # Returning the GUID of the rs.arcObject
    return arc


def move_point(move_from_point, moving_vector, length_modifier=1):
    '''
    Moves a point from a start point, along a vector.
    Parameters:
        move_from_point (tuple): XYZ of the start point
        moving_vector (tuple): XYZ component vector to move point along
        length_modifier (int / float): optional length modifier
    Returns:
        result_point (tuple): XYZ of the resulting point
    '''
    x_coord = move_from_point[0] + moving_vector[0] * length_modifier
    y_coord = move_from_point[1] + moving_vector[1] * length_modifier
    z_coord = move_from_point[2] + moving_vector[2] * length_modifier

    result_point = [x_coord, y_coord, z_coord]

    return result_point


def curve_calc_to_lines(obj):
    '''
    Divides a curve into line segments and outputs gcode.
    This due to the inability and complexity of representing
    complex curves using circles.
    Parameters:
        obj (CurveObject): CurveObject to be calculated
    Returns:
        gcode (string): Resulting gcode output
    '''

    segment_min_length = Decimal('0.1')
    segment_max_length = Decimal('5.5')
    scan_resolution = 0.005

    gcode = ''
    
    gcode += ('\n' + 'G00'
              + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
              + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
              + '\nM12\n')

    curve_divisions= int(rs.CurveLength(obj.guid))
    curve_domain = rs.CurveDomain(obj.guid)

    curve_curvature_min = None
    curve_curvature_max = None

    for i in range (0, curve_divisions):
        curve_parameter = curve_domain[0] + (((curve_domain[1] - curve_domain[0]) / curve_divisions) * i)
        curve_curvature = rs.CurveCurvature(obj.guid, curve_parameter)[3]
        if curve_curvature > curve_curvature_max or curve_curvature_max == None:
            curve_curvature_max = curve_curvature
        if curve_curvature < curve_curvature_min or curve_curvature_min == None:
            curve_curvature_min = curve_curvature

    next_parameter = curve_domain[0]
    current_point = obj.start_point

    # Parameters for a 
    A = -1.97142
    B = 2.9585
    C = 0.0129348
    D = 0

    point_list = []

    print('Steps: ' + str((curve_domain[1] - curve_domain[0]) / scan_resolution))
    while next_parameter < curve_domain[1]:

        length = 0

        curve_curvature = rs.CurveCurvature(obj.guid, next_parameter)[3]
        curvature_normalized = (curve_curvature - curve_curvature_min) / (curve_curvature_max - curve_curvature_min)
        curvature_normalized_cubified = Decimal((A * math.pow(curvature_normalized, 3)
                                                 + B * math.pow(curvature_normalized, 2)
                                                 + C * curvature_normalized
                                                 + D))
        #=======================================================================
        # Linear interpolation
        # value = (C * A) + ((1-C) * B) // convex combination
        # When C equals 0 value equals B.
        # When C equals 1 value equals A.
        # When C equals .5 value equals the average of A and B.
        #=======================================================================
        segment_length = Decimal((curvature_normalized_cubified * segment_max_length) 
                                 + ((1 - curvature_normalized_cubified) * segment_min_length)).quantize(ROUNDING)

        while length < segment_length:
            next_parameter += scan_resolution
            return_point = rs.EvaluateCurve(obj.guid, next_parameter)
            length = rs.VectorLength(rs.VectorCreate(return_point, current_point))

        if next_parameter > curve_domain[1]:
            break

        elif next_parameter <= curve_domain[1] and length >= segment_length:
            point_list.append(current_point)
            current_point = return_point

    if len(point_list):
        for point in point_list:
            if (Decimal(point[0]).quantize(ROUNDING) == Decimal(obj.start_point[0]).quantize(ROUNDING) and
                Decimal(point[1]).quantize(ROUNDING) == Decimal(obj.start_point[1]).quantize(ROUNDING)):
                # Make sure we don't add the first point twice
                pass
            else:
                gcode += ('G01'
                      + ' X' + str(Decimal(point[0]).quantize(ROUNDING))
                      + ' Y' + str(Decimal(point[1]).quantize(ROUNDING))
                      + '\n')
        # Add the last point of the curve to make sure it's a complete cut
        gcode += ('G01'
              + ' X' + str(Decimal(obj.end_point[0]).quantize(ROUNDING))
              + ' Y' + str(Decimal(obj.end_point[1]).quantize(ROUNDING))
              + '\n')

    gcode += ('M22\n')


    return gcode


def ellipse_calc_advanced(obj):
    '''
    Calculates the Five-Centered Arch approximation of an ellipse using 3 circular arcs in each quadrant.
    Algorithm and in-depth reading can be found here: http://mysite.du.edu/~jcalvert/math/ellipse.htm
    '''

    ellipse_quad_points = rs.EllipseQuadPoints(obj.guid)
    center_point = rs.EllipseCenterPoint(obj.guid)

    # Finding A,F,D and O points
    # TODO: Make sure these assumtions are correct
    point_A = ellipse_quad_points[0]
    point_O = center_point
    point_D = ellipse_quad_points[3]

    vector_F = rs.VectorCreate(point_A, point_O)
    point_F = move_point(point_D, vector_F)

    # Using intersections to find H point
    line_AD = rs.AddLine(point_A, point_D)
    intersect = rs.LineClosestPoint(line_AD, point_F)
    # if intersect:
        # rs.AddPoint(intersect)
    line_FH = rs.AddLine(point_F, intersect)
    line_DO = rs.AddLine(point_D, point_O)

    line_line_intersect = rs.LineLineIntersection(line_FH, line_DO)
    if line_line_intersect:
        point_H = line_line_intersect[0]
    # rs.AddLine(point_F, point_H)

    # Finding point K
    vector_OD = rs.VectorCreate(point_D, point_O)
    vector_OD_len = rs.VectorLength(vector_OD)
    vector_OD_dir = rs.VectorUnitize(vector_OD)
    vector_AO = rs.VectorCreate(point_O, point_A)
    vector_AO_dir = rs.VectorUnitize(vector_AO)
    pointK = move_point(point_O, vector_AO_dir, vector_OD_len)

    # Creating circle with AK as diameter
    vector_AK = rs.VectorCreate(pointK, point_A)
    vector_AK_dir = rs.VectorUnitize(vector_AK)
    vector_AK_len = rs.VectorLength(vector_AK)
    circle_K_center = move_point(point_A, vector_AK_dir, vector_AK_len / 2)
    circle_K = rs.AddCircle(circle_K_center, vector_AK_len / 2)

    # Intersecting OD line with circle_K to find LD
    point_Ll = move_point(point_O, vector_OD_dir, vector_AK_len)
    lineOD = rs.AddLine(point_O, point_Ll)
    curve_curve_intersection = rs.CurveCurveIntersection(lineOD, circle_K, tolerance=-1)
    # print str(result[0][0])
    if curve_curve_intersection[0][0] == 1:
        point_L = curve_curve_intersection[0][1]
        # print str(point_L)

    vector_OL = rs.VectorCreate(point_L, point_O)
    vector_OL_len = rs.VectorLength(vector_OL)
    vector_LD = rs.VectorCreate(point_D, point_L)
    point_M = move_point(point_O, vector_LD)

    vector_HM = rs.VectorCreate(point_M, point_H)
    vector_HF = rs.VectorCreate(point_F, point_H)

    arc_M = draw_arc(point_H, vector_HM, vector_HF)

    point_Q = move_point(point_A, vector_AK_dir, vector_OL_len)

    vector_AQ = rs.VectorCreate(point_Q, point_A)
    vector_AQ_len = rs.VectorLength(vector_AQ)

    xa = point_A[0] + vector_AK_dir[0] * vector_AQ_len / 2
    ya = point_A[1] + vector_AK_dir[1] * vector_AQ_len / 2
    za = point_A[2] + vector_AK_dir[2] * vector_AQ_len / 2
    point_P = [xa, ya, za]

    plane = rs.WorldXYPlane()
    plane = rs.MovePlane(plane, point_P)
    planeDeg = rs.VectorAngle([1, 0, 0], vector_AQ)
    # print 'Deg: ' + str(planeDeg)
    plane_cross_product = rs.VectorCrossProduct([1, 0, 0], vector_AQ)[2]
    if plane_cross_product < 0:
        planeDeg = 360 - planeDeg

    plane = rs.RotatePlane(plane, planeDeg, [0, 0, 1])
    arcP = rs.AddArc(plane, vector_AQ_len / 2, -90)
    # print str(result[0][0])
    curve_curve_intersection = rs.CurveCurveIntersection(arc_M, arcP, tolerance=-1)
    if curve_curve_intersection:
        if curve_curve_intersection[0][0] == 1:
            point_N = curve_curve_intersection[0][1]
            # print str(point_L)

    else:
        divide = 50
        arcPpoints = rs.DivideCurve(arcP, divide, create_points=False)
        arc_Mpoints = rs.DivideCurve(arc_M, divide, create_points=False)

        prevLen = None
        smallestLen = None
        Mlist = []
        Plist = []

        for P in arcPpoints:
            for M in arc_Mpoints:
                thisLen = rs.VectorLength(rs.VectorCreate(M, P))
                if thisLen < prevLen or prevLen is None:
                    prevLen = thisLen
                    # print str(prevLen)
                    # rs.AddLine(P, M)
                    Mlist.append(M)
                else:
                    prevLen = prevLen
            if prevLen < smallestLen or smallestLen is None:
                smallestLen = prevLen
                Plist.append(P)

        vecPM = rs.VectorCreate(Mlist[-1], Plist[-1])
        xa = Plist[-1][0] + vecPM[0] / 2
        ya = Plist[-1][1] + vecPM[1] / 2
        za = Plist[-1][2] + vecPM[2] / 2
        point_N = [xa, ya, za]
        print('Total smallest: ' + str(smallestLen))

    draw = False
    if draw:
        rs.AddPoint(point_F)
        rs.AddPoint(point_O)
        rs.AddPoint(point_Q)
        rs.AddPoint(point_M)
        rs.AddPoint(point_L)
    rs.AddPoint(point_N)
    rs.AddPoint(point_P)
    rs.AddPoint(point_H)

    # ellipse_quad_points
    paramList = []
    for qP in ellipse_quad_points:
        param = rs.CurveClosestPoint(obj.guid, qP)
        paramList.append(param)
    trimmedCrv = rs.SplitCurve(obj.guid, paramList, delete_input=False)


    index = 3
    ccparam = rs.CurveClosestPoint(trimmedCrv[index], point_P)
    tangentP = rs.EvaluateCurve(trimmedCrv[index], ccparam)

    vecPtangent = rs.VectorCreate(tangentP, point_P)
    vecPA = rs.VectorCreate(point_A, point_P)


    arcTan1 = draw_arc(point_P, vecPtangent, vecPA)
    
    gcode = ''
    return gcode

def gcode_from_objects(object_list):
    '''
    Function creates gcode from a list of CurveObjects.
    Parameters:
        object_list (CurveObject): List of CurveObjects to evaluate.
    Returns:
        gcode(string): String containing all gcode information processed.
        processed_curve (int): Number of curves processed.
        processed_line (int): Number of lines processed.
        active_length (float): Total distance the laser move and be active cutting / engraving.
        passive_length (float): Total distance the laser will move between cuts / engrave.

    Notes:
        Ellipse: Processed as series of line segments.
        Circle: Processed as two separate arcs, back to back (This to workaround floating point issues).
        Arcs: Processed as arcs, using G02 or G03 circular movement.
        NURBS: Processed as series of line segments.
        Polycurve: Split into sub-curves where sub-curves are processed as arcs.
        Polylines: Slit into sub-lines where sub-lines are processed as lines.
        Lines: Processed as lines, using G00 linear movement.
    '''

    print('Getting gcode from objects')

    #Statistics
    processed_curve = 0
    processed_polycurve = 0
    processed_polyline = 0
    processed_line = 0

    active_length = 0
    passive_length = 0
    previous_position = [0,0,0]

    gcode = ''

    for obj in object_list:

        if obj.curve_type == 'ellipse':

            gcode += curve_calc_to_lines(obj)

            processed_curve += 1
            active_length += rs.CurveLength(obj.guid)


        elif obj.curve_type == 'circle':
            #===================================================================
            # WARNING: 
            # Currently struggling with floating point errors.
            # If start_point + offset - center_point NOT EQUAL 0:
            #     Both GO2 and G03 will fail
            # To work around this, the function will divide the circle in two arcs
            # and work from there. 
            #===================================================================

            curve_domain = rs.CurveDomain(obj.guid)
            #Split circle in two arcs
            sub_curves = rs.SplitCurve(obj.guid, curve_domain[1] / 2, delete_input=False)
            gcode += ('\n' + 'G00'
                      + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
                      + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
                      + '\nM12\n')
            for sub in sub_curves:
                gcode_direction, x_offset, y_offset = arc_calc(sub)
                # G02/G03 [x][y][z]|[i][j][k]
                gcode += str(gcode_direction
                             + ' X' + str(Decimal(rs.CurveEndPoint(sub)[0]).quantize(ROUNDING))
                             + ' Y' + str(Decimal(rs.CurveEndPoint(sub)[1]).quantize(ROUNDING))
                             + ' I' + str(Decimal(x_offset).quantize(ROUNDING))
                             + ' J' + str(Decimal(y_offset).quantize(ROUNDING))
                             + '\n')
                last_entry = (rs.CurveEndPoint(sub)[0], rs.CurveEndPoint(sub)[1])

                if not rs.DeleteObject(sub):
                    print('Unable to delete split curve segment')

            # If there are any rounding errors and the end point of the last arc
            # is not the same as the start point of the first arc, create a line.
            if (((Decimal(last_entry[0]).quantize(ROUNDING))
                != Decimal(obj.start_point[0]).quantize(ROUNDING)) or
                ((Decimal(last_entry[1]).quantize(ROUNDING))
                != Decimal(obj.start_point[1]).quantize(ROUNDING))):

                gcode += ('\n' + 'G01'
                          + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
                          + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
                          )

            gcode += ('M22\n')

            # Add statistics
            processed_curve += 1
            active_length += rs.CurveLength(obj.guid)

        if obj.curve_type == 'arc':

            gcode_direction, x_offset, y_offset = arc_calc(obj.guid)

            x_coord = str(Decimal(obj.end_point[0]).quantize(ROUNDING))
            y_coord = str(Decimal(obj.end_point[1]).quantize(ROUNDING))

            gcode += ('\n' + 'G00'
                      + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
                      + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
                      + '\nM12\n')

            # G02/G03 [x][y][z]|[i][j][k]
            gcode += str(gcode_direction
                        + ' X' + str(x_coord)
                        + ' Y' + str(y_coord)
                        + ' I' + str(Decimal(x_offset).quantize(ROUNDING))
                        + ' J' + str(Decimal(y_offset).quantize(ROUNDING))
                        + '\n')

            gcode += ('M22\n')

            # Add statistics
            processed_curve += 1
            active_length += rs.CurveLength(obj.guid)

        elif obj.curve_type == 'curve':
            #Object is NURBS or interpolated curve

            gcode += curve_calc_to_lines(obj)

            processed_curve += 1
            active_length += rs.CurveLength(obj.guid)

        elif obj.curve_type == 'polycurve':

            sub_curves = rs.ExplodeCurves(obj.guid)

            gcode += ('\n' + 'G00'
                      + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
                      + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
                      + '\nM12\n')

            for sub in sub_curves:
                if rs.IsArc(sub):
                    gcode_direction, x_offset, y_offset = arc_calc(sub)

                    gcode += str(gcode_direction
                                 + ' X' + str(Decimal(rs.CurveEndPoint(sub)[0]).quantize(ROUNDING))
                                 + ' Y' + str(Decimal(rs.CurveEndPoint(sub)[1]).quantize(ROUNDING))
                                 + ' I' + str(Decimal(x_offset).quantize(ROUNDING))
                                 + ' J' + str(Decimal(y_offset).quantize(ROUNDING))
                                 + '\n')
                elif rs.IsLine(sub):
                    gcode += ('G01'
                          + ' X' + str(Decimal(rs.CurveEndPoint(sub)[0]).quantize(ROUNDING))
                          + ' Y' + str(Decimal(rs.CurveEndPoint(sub)[1]).quantize(ROUNDING))
                          + '\n')
                else:
                    curve_divisions= int(rs.CurveLength(sub))
                    curve_domain = rs.CurveDomain(sub)

                    for i in range (0, curve_divisions):
                        curve_parameter = curve_domain[0] + (((curve_domain[1] - curve_domain[0]) / curve_divisions) * i)
                        curve_point = rs.EvaluateCurve(obj.guid, curve_parameter)
                        if curve_point is not None:
                            gcode += ('G01' 
                                      + ' X' + str(Decimal(curve_point[0]).quantize(ROUNDING))
                                      + ' Y' + str(Decimal(curve_point[1]).quantize(ROUNDING))
                                      + '\n')

                if not rs.DeleteObject(sub):
                    print('Unable to delete exploded curve segment')

            gcode += ('M22\n')

            processed_polycurve += 1
            active_length += rs.CurveLength(obj.guid)

        elif obj.curve_type == 'polyline':

            sub_curves = rs.ExplodeCurves(obj.guid)

            gcode += ('\n' + 'G00'
                      + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
                      + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
                      + '\nM12\n')

            for sub in sub_curves:
                gcode += ('G01'
                          + ' X' + str(Decimal(rs.CurveEndPoint(sub)[0]).quantize(ROUNDING))
                          + ' Y' + str(Decimal(rs.CurveEndPoint(sub)[1]).quantize(ROUNDING))
                          + '\n')

                # Delete exploded segments to avoid duplicates
                if not rs.DeleteObject(sub):
                    print('Unable to delete exploded curve segment')

            gcode += ('M22\n')

            processed_polyline += 1
            active_length += rs.CurveLength(obj.guid)

        elif obj.curve_type == 'line':

            gcode += ('\n' + 'G00'
                      + ' X' + str(Decimal(obj.start_point[0]).quantize(ROUNDING))
                      + ' Y' + str(Decimal(obj.start_point[1]).quantize(ROUNDING))
                      + '\nM12\n')

            gcode += ('G01'
                     + ' X' + str(Decimal(obj.end_point[0]).quantize(ROUNDING))
                     + ' Y' + str(Decimal(obj.end_point[1]).quantize(ROUNDING))
                     + '\n')

            gcode += ('M22\n')

            processed_line += 1
            active_length += rs.CurveLength(obj.guid)
        
        passive_move_vector = rs.VectorCreate(obj.start_point, previous_position)
        passive_length += rs.VectorLength(passive_move_vector)
        previous_position = obj.end_point

    return gcode, processed_curve, processed_polycurve, processed_polyline, processed_line, active_length, passive_length


def run_script():
    '''
    Main program function
    TODO: Fix all documentation segments
    '''

    start_time = time.clock()

    #===========================================================================
    # rs.StatusBarProgressMeterShow('Running Gcode Script',
    #                               0,
    #                               100,
    #                               embed_label=True,
    #                               show_percent=True
    #                               )
    #===========================================================================

    print('\n----\n  G-code generator for MultiCAM CO2 laser cutter. \n'
          + '  Version: ' + str(SCRIPT_VERSION)
          + ' by Andreas Weibye(AB), NTNU Trondheim - www.ntnu.edu \n'
          + '  Released under Creative Commons - CC BY-SA 4.0 \n----\n'
         )

    cut_out_of_bounds = 0
    cut_skipped_objects = 0

    engrave_out_of_bounds = 0
    engrave_skipped_objects = 0

    # Getting data from server
    server_data = get_from_url(URL)

    if server_data is False:
        return 1 # Returned with an error but we have notified about it

    if server_data['Offline'] == 1:
        rs.MessageBox(server_data['OfflineMessage'], 0, 'Error: Server is offline')
        return 1

    #===========================================================================
    # rs.StatusBarProgressMeterUpdate(1, absolute=True)
    #===========================================================================

    # Setting the outer bounds of the working area
    global BOUNDS_MAX_X
    global BOUNDS_MAX_Y
    BOUNDS_MAX_X = server_data['Max_X']
    BOUNDS_MAX_Y = server_data['Max_Y']

    if float(server_data['CurrentVersion']) > SCRIPT_VERSION:
        plugin_message = (
            'The laserScript is not up to date. Please download the newest version from '
            + str(server_data['UpdateAddress']) + '\n\n'
            + 'Current version:' + str(server_data['CurrentVersion'])
            + '\nYour script version: ' + str(SCRIPT_VERSION)
            + '\n')

        rs.MessageBox(plugin_message, 0, 'Error: Script out of date')
        return 1

    #===========================================================================
    # rs.StatusBarProgressMeterUpdate(2, absolute=True)
    #===========================================================================

    # Checking the document unit system and terminates if the used does not approve auto-scaling
    if not approve_unit_system():
        rs.MessageBox(
            'Sorry, the laser-cutter only works with millimetres. '
            + 'Try typing \'units\' in Rhino to access settings', 
            0, 'Error: Incompatible unit system')
        return 1

    #===========================================================================
    # rs.StatusBarProgressMeterUpdate(3, absolute=True)
    #===========================================================================

    # Getting cutting and engraving layer
    layer_name_engrave = get_layer_name(_ENGRAVING_LAYER_DEFAULT_NAME)
    layer_name_cut = get_layer_name(_CUTTING_LAYER_DEFAULT_NAME)

    #===========================================================================
    # rs.StatusBarProgressMeterUpdate(10, absolute=True)
    #===========================================================================

    # Terminate if no layer has been selected
    if layer_name_cut == None and layer_name_engrave == None :
        rs.MessageBox(
            'Sorry, you need to select at least a cut or an engrave layer, '
            'alternatively you can make layers titled cut and engrave, which '
            'will be processed automatically', 0, 'Error: No layers processed')
        return 1

    # Getting objects from layers
    objects_engrave = get_objects_from_layer(layer_name_engrave)
    if objects_engrave == False:
        # Duplicate objects found, user exited script
        return 2

    objects_cut = get_objects_from_layer(layer_name_cut)
    if objects_cut == False:
        # Duplicate objects found, user exited script
        return 2

    # Terminate if no objects has been found
    if objects_cut == None and objects_engrave == None:
        rs.MessageBox(
            'Sorry, no objects found on the layers you have selected',
            0, 'Error: No objects found')
        return 1

    # Getting material data
    material_name = list_materials(server_data)

    if material_name is None:
        rs.MessageBox(
            'Sorry, you have to select a material',
            0, 'Error: No material selected')
        return 1

    material_data = server_data['Materials'][material_name]

    #===========================================================================
    # Interpreting curve objects
    #===========================================================================

    if objects_engrave != None:
        #If there are any objects from engrave layer -> sort them
        objects_engrave, engrave_out_of_bounds, engrave_skipped_objects = interpret_curves(objects_engrave)
    else:
        objects_engrave = None

    if objects_cut != None:
        # If there are any objects from cutting layer -> parse and interpret them
        objects_cut, cut_out_of_bounds, cut_skipped_objects = interpret_curves(objects_cut)
    else:
        objects_cut = None

    # Count skipped objects and give option to exit program if any found
    total_out_of_bounds = cut_out_of_bounds + engrave_out_of_bounds
    total_skipped_objects = cut_skipped_objects + engrave_skipped_objects

    if total_out_of_bounds > 0 or total_skipped_objects > 0:
        message_1 = ''
        message_2 = ''

        if total_out_of_bounds > 0:
            message_1 = '%o objects was found to be outside of workable area.' % total_out_of_bounds
        if total_skipped_objects > 0:
            message_2 = '%o objects was skipped for unknown reason.' % total_skipped_objects

        complete_message = message_1 + '\n' + message_2 + '\nExit script and manually fix errors?'

        message = rs.MessageBox(complete_message, 4 | 48 | 0, 'ERROR: Unprocessed objects')
        if message == 6:
            # Yes was clicked
            return 2
        elif message == 7:
            # No was clicked
            # Program continues
            pass

    #===========================================================================
    # Sorting interpreted curve objects
    #===========================================================================

    
    # Sorting objects_engrave
    if objects_engrave != None:
        #If there are any objects interpreted -> sort them
        objects_engrave = sort_advanced(objects_engrave, material_data)
    else:
        objects_engrave = None

    # Sorting objects_cut
    if objects_cut != None:
        # If there are any objects interpreted -> sort them
        objects_cut = sort_advanced(objects_cut, material_data)
    else:
        objects_cut = None


    #===========================================================================
    # Get Gcode and statistics
    #===========================================================================
    algo_start_time = time.clock()

    if objects_engrave != None:
        # Getting gcode_engrave and statistics
        gcode_engrave, curves_engraved, polycurves_engraved, polylines_engraved, lines_engraved, length_engraved_active, length_engraved_passive = gcode_from_objects(objects_engrave)
    else:
        gcode_engrave = None
        curves_engraved = None
        polycurves_engraved = None
        polylines_engraved = None
        lines_engraved = None
        length_engraved_active = 0
        length_engraved_passive = 0

    if objects_cut != None:
        # Getting gcode_cut and statistics
        gcode_cut, curves_cut, polycurves_cut, polylines_cut, lines_cut, length_cut_active, length_cut_passive = gcode_from_objects(objects_cut)
    else:
        gcode_cut = None
        curves_cut = None
        polycurves_cut = None
        polylines_cut = None
        lines_cut = None
        length_cut_active = 0
        length_cut_passive = 0

    print('Calctime: ' + str(time.clock() - algo_start_time))

    duration_engrave = (length_engraved_active / int(material_data['EngravingSpeed'])) + (length_engraved_passive / _G00_SPEED) 
    duration_cut = (length_cut_active / int(material_data['CuttingSpeed'])) + (length_cut_passive / _G00_SPEED)
    duration_total = (duration_engrave + duration_cut) * _ESTIMATE_MODIFIER # Adding x% to estimate to compensate for acceleration

    #===========================================================================
    # Concatenate final gCode
    #===========================================================================

    summary = ('Settings server: \n' + server_data['Name'] + '\n\n'
               + 'Original Rhino file name: ' + str(rs.DocumentName()) + '\n')
    if layer_name_engrave:
        summary += ('Selected engraving layer: ' + str(layer_name_engrave) + '\n')

    if layer_name_cut:
        summary += ('Selected cutting layer: ' + str(layer_name_cut) + '\n')

    summary += ('Generation date and time: ' + str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M%S')) + '\n'
                + 'Selected material profile: ' + str(material_data['MaterialName']) + '\n\n')

    if gcode_engrave:
        if curves_engraved:
            summary += ('Engraving curves processed: ' + str(curves_engraved) + '\n')
        if polycurves_engraved:
            summary += ('Engraving polycurves processed: ' + str(polycurves_engraved) + '\n')
        if polylines_engraved:
            summary += ('Engraving polylines processed: ' + str(polylines_engraved) + '\n')
        if lines_engraved:
            summary += ('Engraving lines processed: ' + str(lines_engraved) + '\n')

        summary += ('Total engraving length: ' + str(int(length_engraved_active)) + ' mm\n'
                    + 'Engraving Time: ' + str(datetime.timedelta(seconds=int(duration_engrave))) + '\n\n')

    if gcode_cut:
        if curves_cut:
            summary += ('Cutting curves processed: ' + str(curves_cut) + '\n')
        if polycurves_cut:
            summary += ('Cutting polycurves processed: ' + str(polycurves_cut) + '\n')
        if polylines_cut:
            summary += ('Cutting polylines processed: ' + str(polylines_cut) + '\n')
        if lines_cut:
            summary += ('Cutting lines processed: ' + str(lines_cut) + '\n')

        summary += ('Total cutting length: ' + str(int(length_cut_active)) + ' mm\n'
                    + 'Cutting Time: ' + str(datetime.timedelta(seconds=int(duration_cut))) + '\n\n')

    summary += ('Skipped objects: ' + str(total_skipped_objects) + '\n'
                + 'Skipped out of bounds objects: ' + str(total_out_of_bounds) + '\n\n'
                + 'Total estimated time to run this file: ' + str(datetime.timedelta(seconds=int(duration_total))) + '\n\n'
                + 'Script 2.0 by Andreas Weibye (AB)\nNTNU Trondheim - www.ntnu.edu')

    gcode_mid = ''

    # Checking if engraveGcode has any info. If yes, adding Gcode for engraving
    if gcode_engrave != None:
        gcode_mid += ('\n(Engraving commands)\n'
                      + 'G97 S' + str(material_data['EngravingPower']) + '\n'
                      + 'G98 P265 E' + str(material_data['EngravingPulse']) + '\n'
                      + 'G01 F' + str(material_data['EngravingSpeed']) + '\n'
                      + str(gcode_engrave) + '\n')

    # Checking if gcode_cut has any info. If yes, adding Gcode for cutting
    if gcode_cut != None:
        gcode_mid += ('\n(Cutting commands)\n'
                      + 'G97 S' + str(material_data['CuttingPower']) + '\n'
                      + 'G98 P265 E' + str(material_data['CuttingPulse']) + '\n'
                      + 'G01 F' + str(material_data['CuttingSpeed']) + '\n'
                      + str(gcode_cut) + '\n')

    gcode_start = ('(\n' + summary + '\n)\n' + '\n'
                   + '(Startup commands) \n'
                   + str(server_data['Start-up']) + '\n'
                   + 'G00 COriginalFilename-' + str(rs.DocumentName()) + '\n'
                   + 'G00 CLaserProfile-' + str(material_data['MaterialName']) + '\n'
                   + 'G00 CTimeEstimate-' + str(datetime.timedelta(seconds=int(duration_total)))
                   + '\n')

    gcode_end = ('(Shutdown commands) \n' + str(server_data['End']))

    # Concatenating final Gcode
    gcode_final = gcode_start + gcode_mid + gcode_end

    # Add G-code to Notes in Rhino Document
    rs.Notes(newnotes=gcode_final)

    # print('Script runtime: ' + str(round(time.clock() - start_time, 6)))

    #===========================================================================
    # Saving file & showing summary
    #===========================================================================
    save_path = rs.SaveFileName('Save Gcode file as (material profile and ending automatically added)')
    if save_path is not None:
        save_file = save_path + '_' + str(material_data['MaterialName']) + '.nc'
    else:
        return 3

    final_file = open(save_file, 'w')

    if final_file is None:
        return 3
    else:
        final_file.write(gcode_final)
        final_file.close()

        # Check if file was created
        if os.path.exists(save_file):
            # TODO: Check if file is larger than 0bytes
            print('File saved successfully')
        else:
            rs.MessageBox('Unable to save file', 0, 'Error')
            return 3

    rs.MessageBox(summary, 0, title='File summary')
    
    return 0



#===============================================================================
# Main programloop
#===============================================================================
if (__name__ == '__main__'):
    exit = run_script()
    if exit == 0:
        print('Program exit: Successful run')
    elif exit == 1:
        print('Program exited with error, but has been notified what caused it')
    elif exit == 2:
        print('Program exit: User chose to exit script')
    elif exit == 3:
        print('Program exit: Error, no notification given')

