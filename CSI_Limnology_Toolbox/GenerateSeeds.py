# Filename: GenerateSeeds.py
# Purpose: Generate seeds for watershed delineation
# from a 24k NHD file geodatabase. Seeds are generated from selected NHDFLowline
# and NHDWaterbody features

import os, shutil
import arcpy
from arcpy import env

arcpy.CheckOutExtension("Spatial")

# User inputs parameters:
nhd = arcpy.GetParameterAsText(0) # User selects a NHD 24k file geodatabase.
snap = arcpy.GetParameterAsText(1) # User selects the corresponding subregion elevation raster.
outfolder = arcpy.GetParameterAsText(2) # User selects the output folder.

# Make a scratch folder
if not os.path.exists(os.path.join(outfolder, "scratch")):
    os.mkdir(os.path.join(outfolder, "scratch"))

scratch = os.path.join(outfolder, "scratch")

# Define Projections
nad83 = arcpy.SpatialReference(4269)
albers = arcpy.SpatialReference(102039)

# Preliminary environmental settings:
env.workspace = nhd
env.snapRaster = snap
env.extent = snap
env.cellSize = 10
env.pyramid = "NONE"
env.outputCoordinateSystem = albers


# Make a layer from NHDWaterbody feature class and select out lakes smaller than a hectare. Project to EPSG 102039.
fcodes = (39000, 39004, 39009, 39010, 39011, 39012,
 43600, 43613, 43615, 43617, 43618, 43619, 43621)
whereClause = '''
"(AreaSqKm" >=0.04 AND "FCode" IN %s\
 OR ("AreaSqKm" >= 0.1 AND "FCode" = 43601)''' % (fcodes,)
waterbody_albers = os.path.join(scratch, "Waterbody_Albers.shp")
arcpy.MakeFeatureLayer_management("NHDWaterbody","Waterbody", whereClause, scratch, "")
arcpy.CopyFeatures_management("Waterbody", waterbody_albers)

# Make a shapefile from NHDFlowline and project to EPSG 102039
arcpy.FeatureClassToShapefile_conversion("NHDFlowline", scratch)
flowline_albers = os.path.join(scratch, "NHDFlowline.shp")

# Add CSI field to flowline_albers and waterbody_albers then calculate unique identifiers for features.
arcpy.AddField_management(flowline_albers, "CSI", "TEXT")
arcpy.CalculateField_management(flowline_albers, "CSI", '''"%s%s" % ("Flowline", !FID!)''', "PYTHON")
arcpy.AddField_management(waterbody_albers, "CSI", "TEXT")
arcpy.CalculateField_management(waterbody_albers, "CSI", '''"%s%s" % ("Waterbody", !FID!)''', "PYTHON")

# Switch to scratch workspace
env.workspace = scratch

# Rasterize flowline_albers and waterbody_albers using "CSI" field for the raster's cell value
flowline_raster = "flowline_raster.tif"
waterbody_raster = "waterbody_raster.tif"
arcpy.PolylineToRaster_conversion(flowline_albers, "CSI", flowline_raster, "", "", 10)
arcpy.PolygonToRaster_conversion(waterbody_albers, "CSI", waterbody_raster, "", "", 10)

# Mosaic the rasters together favoring waterbodies over flowlines.
arcpy.MosaicToNewRaster_management("flowline_raster.tif;waterbody_raster.tif",
            scratch, "seeds_mosaic.tif", albers, "32_BIT_FLOAT",
            "10", "1", "LAST", "LAST")











