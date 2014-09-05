# Filename: WetlandOrder.py
# Purpose: Assigns a class to wetlands based on their connectivity to the landscape.
import os, shutil
import arcpy
from arcpy import env
from arcpy.da import *
from arcpy.sa import *

def split_strahler(stream_area_fc, streams, out_area_fc):
    """This function splits up the NHDArea feature class, which does not
    start and stop polygons at confluences, by creating break points near the
    confluences to split up the polygons. Then, it adds the Strahler value from
    the stream centerline."""
    # 1) Generate euclidean allocation raster from streams (use OBJECTID)
    # 2) Convert euclidean allocation raster to polygons
    # 3) Join allocation polygons "gridcode" to streams "OBJECTID" so that
    #    Strahler value is attached to allocation polygon
    # 4) Use identity function to split up the StreamRiver polygons at the
    #    allocation polygon boundaries, and add the Strahler values
    old_workspace = env.workspace
    env.workspace = 'in_memory'
    cu.multi_msg("Splitting stream area polygons between confluences and joining Strahler order to them...")
    euc = EucAllocation(streams, cell_size = '50', source_field = 'OBJECTID')
    arcpy.RasterToPolygon_conversion(euc, 'allocation_polys')
    arcpy.JoinField_management('allocation_polys', 'grid_code', streams, 'OBJECTID', ['Strahler', 'LengthKm'])
    arcpy.Identity_analysis(stream_area_fc, 'allocation_polys', out_area_fc)
    env.workspace = old_workspace

def wetland_order(rivex, stream_area_fc, nwi, out_fc):
    arcpy.env.extent = "MINOF"
    arcpy.env.workspace = 'in_memory'
    split_strahler(stream_area_fc, rivex, 'stream_area_split')

    # Buffer the stream centerlines and the stream areas and union them together
    arcpy.Buffer_analysis(rixev, "centerline_buffer", "30 meters")
    arcpy.Buffer_analysis('stream_area_split', 'stream_area_buffer', '30 meters')
    arcpy.Union_analysis(['centerline_buffer', 'stream_area_buffer'], 'stream_features_buffered')


    arcpy.Buffer_analysis("allwetpre", "allwet", "30 meters", "OUTSIDE_ONLY")

    # Add wetland order field for connected wetlands
    arcpy.AddField_management("allwet","WetOrder", "TEXT")

    # Spatial join connected wetlands and streams
    ##################Field Maps########################
    fms = arcpy.FieldMappings()
    fm_strahlermax = arcpy.FieldMap()
    fm_strahlersum = arcpy.FieldMap()
    fm_wetorder = arcpy.FieldMap()
    fm_wetha = arcpy.FieldMap()
    fm_attribute = arcpy.FieldMap()
    fm_lengthkm = arcpy.FieldMap()
    fm_csi = arcpy.FieldMap()

    fm_strahlermax.addInputField(rivex, "Strahler")
    fm_strahlersum.addInputField(rivex, "Strahler")
    fm_wetorder.addInputField("allwet", "WetOrder")
    fm_wetha.addInputField("allwet", "WetHa")
    fm_attribute.addInputField("allwet", "ATTRIBUTE")
    fm_lengthkm.addInputField(rivex, "LengthKm")
    fm_csi.addInputField("allwet", "CSI_ID")

    fm_lengthkm.mergeRule = 'Sum'
    fm_strahlermax.mergeRule = 'Max'
    fm_strahlersum.mergeRule = 'Sum'

    lengthkm_name = fm_lengthkm.outputField
    lengthkm_name.name = 'StreamKm'
    lengthkm_name.aliasName = 'StreamKm'
    fm_lengthkm.outputField = lengthkm_name

    strahlermax_name = fm_strahlermax.outputField
    strahlermax_name.name = 'StrOrdMax'
    strahlermax_name.aliasName = 'StrOrdMax'
    fm_strahlermax.outputField = strahlermax_name

    strahlersum_name = fm_strahlersum.outputField
    strahlersum_name.name = 'StrOrdSum'
    strahlersum_name.aliasName = 'StrOrdSum'
    fm_strahlersum.outputField = strahlersum_name

    fms.addFieldMap(fm_strahlermax)
    fms.addFieldMap(fm_strahlersum)
    fms.addFieldMap(fm_wetorder)
    fms.addFieldMap(fm_wetha)
    fms.addFieldMap(fm_attribute)
    fms.addFieldMap(fm_lengthkm)
    fms.addFieldMap(fm_csi)
    #####################################################

    arcpy.SpatialJoin_analysis("allwet", rivex, "conwetorder", '', '', fms)

    # Get the stream count from the join count
    cu.rename_field("conwetorder", 'Join_Count', "StreamCnt", True)

##    # Create output feature class in a file geodatabase
##    arcpy.CreateFileGDB_management(outfolder, "WetlandOrder")
##    outgdb = os.path.join(outfolder, "WetlandOrder.gdb")
##    arcpy.FeatureClassToFeatureClass_conversion("conwetorder", outgdb, "Buffer30m")
##    buffer30m = os.path.join(outgdb,"Buffer30m")
##
##
##
##    outfc = os.path.join(outgdb, "Buffer30m")
##    for field in ['BUFF_DIST', 'ACRES', 'Target_FID', 'Shape_Length']:
##        try:
##            arcpy.DeleteField_management(outfc, field)
##        except:
##            continue

    # Create Veg field
    arcpy.AddField_management(outfc, "Veg", "TEXT")
    arcpy.CalculateField_management(outfc, "Veg", "!ATTRIBUTE![:3]", "PYTHON")

    # Calculate Veg Field
    arcpy.AddField_management(outfc, "VegType", "TEXT")

    with arcpy.da.UpdateCursor(outfc, ["Veg", "VegType"]) as cursor:
        for row in cursor:
            if row[0] == "PEM":
                row[1] = "PEMorPAB"
            elif row[0] == "PAB":
                row[1] = "PEMorPAB"
            elif row[0] == "PFO":
                row[1] = "PFO"
            elif row[0] == "PSS":
                row[1] = "PSS"
            else:
                row[1] = "Other"
            cursor.updateRow(row)

    # Create and calc regime field
    # Because there are no place holders where a classification type is omitted in NWI Codes they are hard to separate...
    arcpy.AddField_management(outfc, "att_", "TEXT") # ex. "PFO1A_"
    arcpy.AddField_management(outfc, "att3", "TEXT") # ex. "PFO*"
    arcpy.AddField_management(outfc, "att4", "TEXT") # ex "PFO1*"
    arcpy.AddField_management(outfc, "Regime", "TEXT") # This will hold final value. ex. "E"
    att_ = '''!ATTRIBUTE! + "____"'''
    att3 = "!att_![3]"
    att4 = "!att_![4]"
    arcpy.CalculateField_management(outfc, "att_", att_, "PYTHON")
    arcpy.CalculateField_management(outfc, "att3", att3, "PYTHON")
    arcpy.CalculateField_management(outfc, "att4", att4, "PYTHON")

    # So we run a cursor...            row[0]  row[1]   row[2]
    with arcpy.da.UpdateCursor(outfc, ["att3", "att4", "Regime"]) as cursor:
        for row in cursor:
            if row[0].isdigit():  # if the 4th character is a number (subclass) the next number is the regime
                row[2] = row[1]
            elif row[0].isupper(): # if the 4th character is an upper case letter it is the regime
                row[2] = row[0]
            elif row[0].islower(): # if the 4th character is a lower case letter there's no water regime
                row[2] = "unknown"
            elif row[1] == "/":     # if there are multiple clasifications the regime is unknown
                row[2] = "unknown"
            else:                   # if there's some other odd character the regime is unknown.
                row[2] = "unknown"

            cursor.updateRow(row)

    # Then we run another cursor...     row[0]
    with arcpy.da.UpdateCursor(outfc, ["Regime"]) as cursor:
        for row in cursor:
            if row[0] == "/":
                row[0] = "unknown"

            cursor.updateRow(row)

    arcpy.DeleteField_management(outfc, "att_")
    arcpy.DeleteField_management(outfc, "att3")
    arcpy.DeleteField_management(outfc, "att4")

    # Calculate WetOrder from StrOrdSum
    with arcpy.da.UpdateCursor(outfc, ["StrOrdSum", "WetOrder"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                row[1] = "Isolated"
            elif row[0] == 1:
                row[1] = "Single"
            elif row[0] == None:
                row[1] = "Isolated"
            else:
                row[1] = "Connected"
            cursor.updateRow(row)

    # Delete intermediate veg field
    arcpy.DeleteField_management(outfc, "Veg")
    try:
        arcpy.DeleteField_management(outfc, "Shape_Length")
        arcpy.DeleteField_management(outfc, "Shape_Area")
    except:
        pass

    # Join fields from buffer rings back to original polygons.
    arcpy.JoinField_management("allwetpre", "CSI_ID", buffer30m, "CSI_ID", ["WetOrder","StrOrdSum","StrOrdMax","StreamCnt","StreamKm", "VegType", "Regime"])
    arcpy.FeatureClassToFeatureClass_conversion("allwetpre", outgdb, "WetlandOrder")

def main():
    # User input parameters:
    rivex = arcpy.GetParameterAsText(0) # A shapefile of rivers that has the "Strahler" field produced by RivEx extension.
    stream_area_fc = arcpy.GetParameterAsText(1) # shapefile of NHDAreas merged together with duplicates deleted
    nwi = arcpy.GetParameterAsText(1) # NWI feature class
    outfolder = arcpy.GetParameterAsText(2) # Location where output gets stored.

if __name__ == '__main__':
    main()
























