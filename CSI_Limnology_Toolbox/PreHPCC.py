# Filename: PreHPCC.py
# Purpose: Mosaic NEDs to NHD subregions, burn streams and clip output to HUC8 boundaries.

import os, shutil
import arcpy
from arcpy.sa import *
from arcpy import env
import csiutils as cu

#################################################################################################################################################
# Burning Streams

def burn(subregion_ned, nhd_gdb, burnt_out, projection = arcpy.SpatialReference(102039)):
    env.snapRaster = subregion_ned
    env.outputCoordinateSystem = projection
    env.compression = "LZ77" # compress temp tifs for speed
    env.workspace = nhd_gdb

    # Copy flowlines to shapefile that will inherit environ output coord system
    flow_line = "NHDFlowline_Projected"
    if not arcpy.Exists(flow_line):
        arcpy.FeatureClassToFeatureClass_conversion("NHDFlowline", nhd_gdb, flow_line)

    cu.multi_msg("Prepared NHDFlowline for rasterizing.")

    # Feature to Raster- rasterize the NHDFlowline
    flow_line_raster = "in_memory/flow_line_raster"
    arcpy.FeatureToRaster_conversion(flow_line, "OBJECTID", flow_line_raster, "10")
    cu.multi_msg("Converted flowlines to raster.")

    # Raster Calculator- burns in streams, beveling in from 500m
    cu.multi_msg("Burning streams into raster, 10m deep and beveling in from 500m out. This may take a while....")
    distance = EucDistance(flow_line, cell_size = "10")
    streams = Reclassify(Raster(flow_line_raster) > 0, "Value", "1 1; NoData 0")
    burnt = Raster(subregion_ned) - (10 * streams) - (0.02 * (500 - distance) * (distance < 500))

    cu.multi_msg("Saving output raster...")
    burnt.save(burnt_out)

    # Delete intermediate rasters and shapefiles
    cu.cleanup([flow_line, flow_line_raster])
    cu.multi_msg("Burn process completed")

###############################################################################################################################################

def clip(raster, nhd_gdb, projection, outfolder):

    env.workspace = nhd
    env.outputCoordinateSystem = projection
    env.compression = "NONE" # only final tifs are generated
    env.pyramid = "NONE"

    # Create a feature dataset in NHD file geodatabase named "HUC8_Albers" in Albers projection
    out_feature_dataset = "HUC8_Albers"
    arcpy.CreateFeatureDataset_management(env.workspace, out_feature_dataset, projection)
    arcpy.RefreshCatalog(nhd)

    # HUC8 polygons each saved as separate fc inheriting albers from environ
    huc8_fc = "WBD_HU8"
    field = "HUC_8"
    arcpy.MakeFeatureLayer_management(huc8_fc, "huc8_layer")

    with arcpy.da.SearchCursor(huc8_fc, field) as cursor:
        for row in cursor:
            if row[0].startswith(nhdsubregion):
                whereClause = ''' "%s" = '%s' ''' % (field, row[0])
                arcpy.SelectLayerByAttribute_management("huc8_layer", 'NEW_SELECTION', whereClause)
                arcpy.CopyFeatures_management("huc8_layer", os.path.join(out_feature_dataset, "HUC" + row[0]))

    #retrieve only the single huc8 fcs and not the one with all of them
    fcs = arcpy.ListFeatureClasses("HUC%s*" % nhdsubregion, "Polygon", out_feature_dataset)
    fcs_buffered = [os.path.join(out_feature_dataset, fc + "_buffer") for fc in fcs]
    out_clips = [os.path.join(outfolder, "huc8clips" + nhdsubregion,
    "NED" + fc[3:] + ".tif") for fc in fcs]

    # Buffer HUC8 feature classes by 5000m
    for fc, fc_buffered in zip(fcs, fcs_buffered):
        arcpy.Buffer_analysis(fc, fc_buffered, "5000 meters")

    cu.multi_msg("Created HUC8 buffers.")
    arcpy.RefreshCatalog(nhd)

    # Clips rasters
    cu.multi_msg("Starting HUC8 clips...")
    for fc_buffered, out_clip in zip(fcs_buffered, out_clips):
        arcpy.Clip_management(raster, '', out_clip, fc_buffered, "0", "ClippingGeometry")

    arcpy.Compact_management(nhd)

    cu.multi_msg("Clipping complete.")

#END OF DEF clip

# "Output" is mosaic with file path = subregion_ned
def main():
    subregion_ned = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    burnt_out = arcpy.GetParameterAsText(2)
    projection = arcpy.GetParameter(3)
    input_burnt = arcpy.GetParameter(4)

    arcpy.CheckOutExtension("Spatial")

    if not input_burnt:
        burn(subregion_ned, nhd_gdb, burnt_out, projection)
        input_burnt = burnt_out
    try:
        clip(input_burnt, nhd_gdb, projection, outfolder)
        arcpy.Delete_management(input_burnt)
        cu.multi_msg("Complete. HUC8 burned clips are now ready for flow direction.")
    except arcpy.ExecuteError:
        cu.multi_msg("Clip failed, try again. Mosaic file is %s and burnt NED file is %s" %
        (subregion_ned, burnt_ned))
        arcpy.AddError(arcpy.GetMessages(2))
    except Exception as e:
        cu.multi_msg("Clip failed, try again. Mosaic file is %s and burnt NED file is %s" %
        (subregion_ned, burnt_ned))
        cu.multi_msg(e.message)
    finally:
        arcpy.CheckInExtension("Spatial")

def test():
    subregion_ned = 'C:/GISData/Scratch/NHD0109/NED13_0109.tif'
    nhd_gdb = 'C:/GISData/Scratch/NHD0109/NHDH0109.gdb'
    burnt_out = 'C:/GISData/Scratch/Burnt_0109.tif'
    input_burnt = ''

    arcpy.CheckOutExtension("Spatial")

    if not input_burnt:
        burn(subregion_ned, nhd_gdb, burnt_out)
        input_burnt = burnt_out
##    try:
##        clip(input_burnt, nhd_gdb, projection, outfolder)
##        arcpy.Delete_management(input_burnt)
##        cu.multi_msg("Complete. HUC8 burned clips are now ready for flow direction.")
##    except arcpy.ExecuteError:
##        cu.multi_msg("Clip failed, try again. Mosaic file is %s and burnt NED file is %s" %
##        (subregion_ned, burnt_ned))
##        arcpy.AddError(arcpy.GetMessages(2))
##    except Exception as e:
##        cu.multi_msg("Clip failed, try again. Mosaic file is %s and burnt NED file is %s" %
##        (subregion_ned, burnt_ned))
##        cu.multi_msg(e.message)
##    finally:
##        arcpy.CheckInExtension("Spatial")

if __name__ == "__main__":
    main()