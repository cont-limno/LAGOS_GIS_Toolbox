import collections, os, random, sys, tempfile
import arcpy
import numpy

# All of the following is from the ESRI Spatial Analyst team's tool called
# "Zonal Statistics as Table for Overlapping Features"
def colorPolygons(feature_class, feature_field, out_directory):
    arcpy.env.overwriteOutput = True

    # Create temporary directory
    temp_dir = os.path.join(tempfile.gettempdir(), 'zonal')
    index = 0
    while os.path.exists(temp_dir):
        temp_dir = os.path.join(tempfile.gettempdir(), 'zonal%d' % index)
        index += 1
    os.mkdir(temp_dir)


    # Initialize variables
    temp_features = os.path.join(temp_dir, "dissolve.shp")
    bldissolved = False
    # Dissolve on non-ObjectID field
    desc = arcpy.Describe(feature_class)
    arcpy.AddMessage("Dissolving features.")
    if hasattr(desc, "OIDFieldName"):
        if feature_field != desc.OIDFieldName:
            arcpy.Dissolve_management(feature_class, temp_features, \
                feature_field)
            bldissolved = True
        else:
            temp_features = feature_class
    else:
        arcpy.Dissolve_management(feature_class, temp_features, \
            feature_field)
        bldissolved = True
    # Get ObjectID field from dissolved
    if bldissolved:
        desc = arcpy.Describe(temp_features)
        oid_field = desc.OIDFieldName
    else:
        oid_field = feature_field

    # Calculate polygon contiguity
    arcpy.AddMessage("Identifying overlapping polygons...")
    arcpy.env.outputMFlag = "Disabled"
    result = arcpy.PolygonNeighbors_analysis(temp_features,
        'in_memory/neighbors', oid_field, "AREA_OVERLAP", "BOTH_SIDES")
    if 'WARNING 000117:' in result.getMessages(1):
        arcpy.AddError("Input feature zone data: {} does not contain "
                        "overlapping features.".format(temp_features))
        sys.exit(1)


    arcpy.AddMessage("Identified overlapping polygons.")
    print("Identified overlapping polygons.")

    arcpy.AddMessage("Calculating feature subsets without overlaps...")
    print("Calculating feature subsets without overlaps...")


    # Retrieve as array with columns src_FID and nbr_FID
    arr = arcpy.da.TableToNumPyArray('in_memory/neighbors',
        ['src_%s' % oid_field, 'nbr_%s' % oid_field])
    arr = numpy.array(arr.tolist())

    # Retrieves the colors of the neighboring nodes
    def get_colors(nodes, neighbors):
        colors = set()
        for neighbor in neighbors:
            colors.add(nodes[neighbor][0])
        colors.difference([0])
        return colors

    # Create a new color
    def get_new_color(colors):
        return max(colors)+1 if len(colors) > 0 else 1

    # Chooses from existing colors randomly
    def choose_color(colors):
        return random.choice(list(colors))

    # Sort source FIDs in descending order by number of neighbors
    arr_uniq = numpy.unique(arr[:,0])
    arr_count = numpy.zeros_like(arr_uniq)
    for index in range(arr_uniq.size):
        arr_count[index] = numpy.count_nonzero(arr[:, 0] == arr_uniq[index])
    arr_ind = numpy.argsort(arr_count)[::-1]

    # Initialize node dictionary --
    #   where key := FID of feature (integer)
    #   where value[0] := color of feature (integer)
    #   where value[1] := FIDs of neighboring features (set)
    nodes = collections.OrderedDict()
    for item in arr_uniq[arr_ind]:
        nodes[item] = [0, set()]
    # Populate neighbors
    for index in range(arr.shape[0]):
        nodes[arr[index, 0]][1].add(arr[index, 1])

    # Color nodes --
    colors = set()
    for node in nodes:
        # Get colors of neighboring nodes
        nbr_colors = get_colors(nodes, nodes[node][1])
        # Search for a color not among those colors
        choices = colors.difference(nbr_colors)
        # Assign the node that color or create it when necessary
        if len(choices) == 0:
            new_color = get_new_color(colors)
            colors.add(new_color)
            nodes[node][0] = new_color
        else:
            nodes[node][0] = choose_color(choices)

    # Classify nodes by colors --
    classes = {}
    for node in nodes:
        color = nodes[node][0]
        if color in classes:
            classes[color].add(node)
        else:
            classes[color] = set([node])

    # Get set of all FIDs
    all_fids = set()
    with arcpy.da.SearchCursor(temp_features, oid_field) as cursor:
        for row in cursor:
            all_fids.add(row[0])

    # Add disjoint FIDs to new class if necessary
    disjoint_fids = all_fids.difference(set(nodes.keys()))
    if len(disjoint_fids) > 0:
        new_color = get_new_color(colors)
        classes[new_color] = disjoint_fids

    # Calculate number of classes
    num_classes = len(classes)

    # Save each class
    temp_lyr = "temp_layer"
    cl_separator = ' OR \"%s\" = ' % oid_field
    for index, cl in enumerate(classes):
        arcpy.SetProgressorLabel(
            "Processing layer %d of %d..." % (index+1, num_classes))
        where_clause = '\"%s\" = %s' % (oid_field, \
            cl_separator.join(map(str, classes[cl])))
        temp_table = os.path.join(temp_dir, "zone_%d.dbf" % index)
        arcpy.MakeFeatureLayer_management(temp_features, temp_lyr, \
            where_clause)

        # This part added by Nicole
        # Save polygon layers to output folder
        outLayerBase = os.path.splitext(os.path.basename(feature_class))[0]
        outLayerName = arcpy.CreateUniqueName(outLayerBase + "_NoOverlap.shp", out_directory)
        print("Saving feature class %s of %s with name %s" % (str(index + 1),
            str(len(classes)), outLayerName))
        arcpy.CopyFeatures_management(temp_lyr, outLayerName)
        arcpy.Delete_management(temp_lyr)
    return out_directory

def test():
    feature_class = r'C:\GISData\Master_Geodata\MasterGeodatabase2014.gdb'
    feature_field = 'NHD_ID'
    out_directory = 'C:/GISData/Scratch/Test_ZonalOverlap_FULL'
    colorPolygons(feature_class, feature_field, out_directory)

def main():
    feature_class = arcpy.GetParameterAsText(0)
    feature_field = arcpy.GetParameterAsText(1)
    out_directory = arcpy.GetParameterAsText(2)
    colorPolygons(feature_class, feature_field, out_directory)

if __name__ == '__main__':
    main()
