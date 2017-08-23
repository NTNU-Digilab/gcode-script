import json
import urllib
import rhinoscriptsyntax as rs
import rhinoscript
import Rhino
import scriptcontext
import datetime

# Global Variables

url = 'http://www.ntnu.no/ab/digilab/Web/laser.json'
plugin_version = 1.0

__commandname__ = "laser"


def fetch_from_url(url):
    print "Fetching Settings from Server"
    try:
        json_data = urllib.urlopen(url)
    except: 
        rs.MessageBox("Cannot connect to online laser settings - are you sure you are online?", 0)
        return False

    try:
        data = json.load(json_data)
    except: 
        rs.MessageBox("Something went wrong downloading the settings from the server. Contact the laser people to figure out who is to blame", 0)
        return False

    json_data.close()
    return data

def list_materials(data, title = "Choose material"):
    print "Generating material list from server"
    material_index = 0
    items = [data["Materials"][i]["MaterialName"] for i in range(len(data["Materials"]))] 
    material = rs.GetString(title, None, items)
    for i in range(len(data["Materials"])):
        if material == data["Materials"][i]["MaterialName"]:
            material_index = i
        elif material == None:
            return None
    return material_index

def approve_unit_system():
    print "Checking system units"
    if rs.UnitSystem() != 2:
        unit_system = rs.MessageBox("The document\'s unit system has to be set to millimeters because that is the only thing the laser knows how to read.\
        \n\nThis can be done with auto-scaling (if you have designed with other units) or by converting only (if everything is meants to be in mm, but the units are just wrong) \
        \n\nDo you wish to auto-scale everything in the conversion process?", buttons=3, title="Document has wrong units")
        if unit_system == 6:
            rs.UnitSystem(2, True)
            print "Unit system set to millimeters with auto-scaling."
            return True
        elif unit_system == 7:
            rs.UnitSystem(2, False)
            print "Unit system set to millimeters with auto-scaling."
            return True
        else:
            return False
    return True

def bounding_box(ob):
    """Returns bounding box for an object."""
    if ob:
        bbox = rs.BoundingBox(ob)
        x_coor = [bbox[i][0] for i in range(len(bbox))]
        y_coor = [bbox[i][1] for i in range(len(bbox))]

        return min(x_coor), max(x_coor), min(y_coor), max(y_coor)

def get_cut_layer():
    print "Getting cutting layer"
    cut_found = False
    layers = rs.LayerNames()
    if layers:
        for layer in layers:
            if (layer.lower() == "cut"):
                cut_found = True
                print "Found layer: cut"
                return layer
        if not cut_found:
            layers.append('None')
            cut_layer = rs.GetString("Choose layer for cutting", None, layers)
            if cut_layer == 'None':
                print 'No cut layer chosen'
                return None
            elif cut_layer == False:
                print 'No cut layer chosen'
                return None
            elif cut_layer not in layers:
                print 'No such layer found'
                return None
            return cut_layer
        
def get_engrave_layer():
    print "Getting engraving layer"
    engrave_found = False
    layers = rs.LayerNames()
    if layers:
        for layer in layers:
            if (layer.lower() == "engrave"):
                engrave_found = True
                print "Found layer: engrave"
                return layer
        if not engrave_found:
            layers.append('None')
            engrave_layer = rs.GetString("Choose layer for engraving", None, layers)
            if engrave_layer == 'None':
                print 'No engrave layer chosen'
                return None
            elif engrave_layer == False:
                print 'No engrave layer chosen'
                return None
            elif engrave_layer not in layers:
                print 'No such layer found'
                return None
            return engrave_layer      

def get_objects_from_layer(layername):
    if layername == None:
        return None
    print "Getting objects from layer: " + str(layername)
    objects = rs.ObjectsByLayer(layername, False)
    if not objects:
        rs.MessageBox("Layer has no objects: " + str(layername), 0)
        return None

    return objects

#Get points

def process_line(line_id):
    line_output = []
    line_output.append(rs.CurveStartPoint(line_id))
    line_output.append(rs.CurveEndPoint(line_id))
    return line_output

def process_polyline(polyline_id):
    polyline_output = []
    points = rs.PolylineVertices(polyline_id)
    for point in points: 
        polyline_output.append(point)
    
    polyline_output.append(rs.CurveEndPoint(polyline_id))
    return polyline_output

def process_curve(curve_id):
    curve_output = []
    #Get the number of Divisions
    curve_divisions = int(rs.CurveLength(curve_id))
    
    if (curve_divisions is None):
        return

    #Get the number of Curve Domains
    curve_domain = rs.CurveDomain(curve_id, 0)

    if (curve_domain is None):
        return


    for i in range(0, curve_divisions):

        curve_param = curve_domain[0] + (((curve_domain[1] - curve_domain[0]) / (curve_divisions)) * i)

        curve_point = rhinoscript.curve.EvaluateCurve(curve_id, curve_param)

        if (curve_point is not None):

            curve_output.append(curve_point)
            
    curve_output.append(rs.CurveEndPoint(curve_id))
    return curve_output

# Sorting and other stuff

def pt_to_gcode(dpts):
    # generates G-code from a set of points
    gcode = ''
    ptzero = dpts[0]
    gzero = str("G00 X" + str(round(ptzero[0],3)) + " Y" + str(round(ptzero[1],3)))
    gcode += gzero + '\n'
    gcode += 'M12' + '\n'
    
    for pt in dpts:
        gcodeline = str("G01 X" + str(round(pt[0],3)) + " Y" + str(round(pt[1],3)))
        gcode += gcodeline + '\n'
    gcode += 'M22' + '\n'

    return gcode

def sort_layer(layer):
    print "Sorting layer."
    
    #Variables
    
    closed_curves = []
    closed_curve_areas = []
    open_curves = []
    sorted_list = []
    
    #Divide objects into closed and open curves
    
    for obj in layer:
        if rs.IsCurveClosed(obj):
            closed_curves.append(obj)
        else:      
            open_curves.append(obj)

    #Calculate area of each closed curve

    for obj in closed_curves:
        try:
            # Try solves issue of two duplicate lines forming a closed curve without area, adds zero to list
            area = rs.CurveArea(obj)
            closed_curve_areas.append(area[0])
        except:
            closed_curve_areas.append(0)

    #Sort closed curves based on area, smallest first.

    sorted_closed_curves = [closed_curves for closed_curve_areas, closed_curves in sorted(zip(closed_curve_areas, closed_curves))]
    sorted_closed_curves.reverse()

    # Combine lists

    sorted_list.append(open_curves)
    sorted_list.append(reversed(sorted_closed_curves))

    return sorted_list

def process_objects(obj_ids, data):
    print "Generating G-code from objects"


    obj_ids_lines = []
    obj_ids_pc = []
    obj_ids_pc_delete = []
    gcode_points = []
    output = []

    o_o_b = 0
    s_objects = 0
    
    clength = 0.0
    clines = 0
    cpolylines = 0
    ccurves = 0

    flat_list = [image for mi in obj_ids for image in mi]

    obj_clean = [x for x in flat_list if x]

    for obj in obj_clean:
        if rs.IsPolyCurve(obj):
            c_layer = rs.ObjectLayer(obj)
            segments = rs.ExplodeCurves(obj)
            for x in segments:
                rs.ObjectLayer(x, c_layer)
                obj_ids_pc.append(x)
                obj_ids_pc_delete.append(x)
        else:
            obj_ids_pc.append(obj)

    
    for obj_id in obj_ids_pc:
    
        #Checks if the object is out of bounds (also needs to check for machine dimensions...)
        min_x, max_x, min_y, max_y = bounding_box(obj_id)
        if (min_x < 0) or (min_y < 0):
           o_o_b += 1
        elif (max_x > data["Max_X"]) or (max_y > data["Max_Y"]):
           o_o_b += 1
        else:
            clength += rs.CurveLength(obj_id)
            if rs.IsLine(obj_id):
                # Lines
                gcode_points = process_line(obj_id)
                # Her maa man ta en try fordi process_line kan streike, hvis den gir false maa man +1 skipped obj + return
                g_code = pt_to_gcode(gcode_points)
                clines +=1
                output.append(g_code)
                
            elif rs.IsPolyline(obj_id):
                # Polylines
                gcode_points = process_polyline(obj_id)
                # Her maa man ta en try fordi process_line kan streike, hvis den gir false maa man +1 skipped obj + return
                g_code = pt_to_gcode(gcode_points)
                cpolylines +=1
                output.append(g_code)

            elif rs.IsCurve(obj_id):      
                # Curves
                gcode_points = process_curve(obj_id)
                # Her maa man ta en try fordi process_line kan streike, hvis den gir false maa man +1 skipped obj + return
                g_code = pt_to_gcode(gcode_points)
                ccurves +=1
                output.append(g_code)
            else:      
                # Other objects
                skipped_objects += 1
    
    for x in obj_ids_pc_delete:
    	rs.DeleteObject(x)

    return output, clength, clines, cpolylines, ccurves, o_o_b, s_objects 

#RunCommand is called when the user enters the command name in Rhino.

def run_command(is_interactive):
    
    print "\n\n----\n  G-code generator for Lasercutting \n  Version: " + str(plugin_version) + " \n  by Asbjorn Steinskog (IDI) and Pasi Aalto (AB), NTNU Trondheim - www.ntnu.edu \n  Released under Creative Commons - CC BY-SA 4.0 \n----\n"
    
    out_of_bounds_c = 0
    skipped_objects_c = 0
    cutting_length = 0.0
    cutting_lines = 0
    cutting_polylines = 0
    cutting_curves = 0
    
    out_of_bounds_e = 0
    skipped_objects_e = 0
    engrave_length = 0.0
    engrave_lines = 0
    engrave_polylines = 0
    engrave_curves = 0

    data = fetch_from_url(url)
    if data is False:
        return

    #if data["Offline"] == 1:
    #    rs.MessageBox(data["OfflineMessage"], 0, "The server is offline")
    #    return

    if float(data["CurrentVersion"]) > plugin_version:
        plugin_message = ("The laser plugin is not up to date. Please download and install a new version from " + str(data["UpdateAddress"]) + " \n\n" +
                            "Current version:" + str(data["CurrentVersion"]) + "\n"
                            "Your plugin version:" + str(plugin_version) + "\n")
        rs.MessageBox(plugin_message, 0)
        return

    #Terminate if the user doesn't approve auto-scaling.
    if not approve_unit_system():
        rs.MessageBox("Sorry, plugin only works with millimeters. Try typing 'units' in Rhino to access settings", 0)
        return


    #Make list with objects from cut and engrave objects
    engrave_layer_a = get_engrave_layer()
    cut_layer_a = get_cut_layer()

    if cut_layer_a == None and engrave_layer_a == None:
        rs.MessageBox("Sorry, you need to select at least a cut or an engrave layer, alternatively you can make layers titled cut and engrave, which will be processed automatically", 0)
        return

    engrave_objects_a = get_objects_from_layer(engrave_layer_a)

    cut_objects_a = get_objects_from_layer(cut_layer_a)



    if cut_objects_a == None and engrave_objects_a == None:
        rs.MessageBox("Sorry, there are no objects on the layers you selected", 0)
        return

    #Get Materials

    mat=list_materials(data)
    if mat == None:
        rs.MessageBox("Sorry, You have to select a material", 0)
        return

    material_data = data["Materials"][mat]


    #Sort objects

    if engrave_objects_a != None:
        engrave_objects = sort_layer(engrave_objects_a)
    else:
    	engrave_objects = None

    if cut_objects_a != None:
        cut_objects = sort_layer(cut_objects_a)
    else:
    	cut_objects = None
    
    #Process objects to G-code and get all the statistics

    if engrave_objects !=None:
        engrave_gcode, engrave_length, engrave_lines, engrave_polylines, engrave_curves, out_of_bounds_c, skipped_objects_e = process_objects(engrave_objects, data)
    else:
        engrave_gcode = None

    if cut_objects !=None:
        cut_gcode, cutting_length, cutting_lines, cutting_polylines, cutting_curves, out_of_bounds_e, skipped_objects_c = process_objects(cut_objects, data)
    else:
    	cut_gcode = None

    if engrave_gcode !=None:
        engrave_gcode_exists = engrave_gcode
    else:
        engrave_gcode_exists = []

    if cut_gcode !=None:
        cut_gcode_exists = cut_gcode
    else:
        cut_gcode_exists = []

    # Get Document Name
    doc_name = rs.DocumentName()
    #Calculate statistics

    out_of_bounds = out_of_bounds_c + out_of_bounds_e
    skipped_objects = skipped_objects_c + skipped_objects_e
    
    engraving_time = int(engrave_length) / int(material_data["EngravingSpeed"])
    cutting_time = int(cutting_length) / int(material_data["CuttingSpeed"])
    total_time = engraving_time + cutting_time

    now = datetime.datetime.now()

    #Concatenate final G-code

    summary = ("Settings Server: \n" + data["Name"] + '\n\n'
             + "Original Rhino File Name: " + str(rs.DocumentName()) + '\n'
             + "Selected Cutting layer: " + str(cut_layer_a) + '\n'
             + "Selected Engraving layer: " + str(engrave_layer_a) + '\n'
             + "Generation date and time: " + str(now.strftime('%Y-%m-%d %H:%M:%S')) + '\n'
    	     + "Selected Material Profile: " + str(material_data["MaterialName"]) + '\n\n'
    	     + "Cutting Lines processed: " + str(cutting_lines) + "\n"
             + "Cutting Polylines processed: " + str(cutting_polylines) + "\n"
             + "Cutting Curves processed: " + str(cutting_curves) + "\n"
             + "Total Cutting Length: " + str(int(cutting_length)) + " mm\n"
             + "Cutting Time: " + str(datetime.timedelta(seconds = int(cutting_time))) + "\n\n"
              
             + "Engraving Lines processed: " + str(engrave_lines) + "\n"
             + "Engraving Polylines processed: " + str(engrave_polylines) + "\n"
             + "Engraving Curves processed: " + str(engrave_curves) + "\n"
             + "Total Engraving Length: " + str(int(engrave_length)) + " mm\n\n"
             + "Engraving Time: " + str(datetime.timedelta(seconds = int(engraving_time))) + "\n\n"
             
             + "Skipped objects: " + str(skipped_objects) +"\n"
             + "Skipped out of bounds objects: " + str(out_of_bounds) +"\n\n"
             + "Total Time: " + str(datetime.timedelta(seconds = int(total_time))) + "\n\n"
             + "Script by Asbjorn Steinskog (IDI) and Pasi Aalto (AB)\nNTNU Trondheim - www.ntnu.edu\n\n")

    final_gcode = ("(\n" + summary + "\n)\n\n"
    	            + '\n'
    	            + str(data["Start-up"])
                    + '\n'
                    + 'G00 COriginalFilename-' + str(rs.DocumentName())
                    + '\n'
                    + 'G00 CLaserProfile-' + str(material_data["MaterialName"])
                    + '\n'
                    + 'G00 CTimeEstimate-' + str(datetime.timedelta(seconds = int(total_time)))		
                    + '\n'
                    + 'G97 S' + str(material_data["EngravingPower"])
                    + '\n'
                    + 'G98 P265 E' + str(material_data["EngravingPulse"])
                    + '\n'
                    + 'G01 F' + str(material_data["EngravingSpeed"])
                    + '\n'
                    + '\n'.join(map(str, engrave_gcode_exists))
                    + 'G97 S' + str(material_data["CuttingPower"])
                    + '\n'
                    + 'G98 P265 E' + str(material_data["CuttingPulse"])
                    + '\n'
                    + 'G01 F' + str(material_data["CuttingSpeed"])
                    + '\n'
                    + '\n'.join(map(str, cut_gcode_exists))
                    + str(data["End"]))
    
    # Add G-code to Notes in Rhino Document
    rs.Notes(newnotes=final_gcode)

    print "\n\nTotal Time: " + str(datetime.timedelta(seconds = int(total_time))) + "\n"
 
    # Save file

    savepath = rs.SaveFileName("Save laser file as (material profile and ending automatically added)")
    if savepath is not None:
        savefile = savepath + '_' + str(material_data["MaterialName"]) + '.nc'
    else:
        return

    

    finalfile = open(savefile, 'w')

    if (finalfile is None):
        return
    else:
        finalfile.write(final_gcode)
        finalfile.close()
    
   


    
    rs.MessageBox(summary, 0)

if (__name__ == "__main__"):
        run_command(True)
