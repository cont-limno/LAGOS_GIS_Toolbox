# Filename: GenerateSeeds.py
# Purpose: Generate seeds for watershed delineation from a 24k NHD file geodatabase.

import os
import arcpy
arcpy.CheckOutExtension("Spatial")
from arcpy.sa import *
from arcpy import env
import shutil

# User inputs parameters:
nhd = arcpy.GetParameterAsText(0) # User selects a NHD 24k file geodatabase.
snap = arcpy.GetParameterAsText(1) # User selects the corresponding subregion elevation raster.
outfolder = arcpy.GetParameterAsText(2) # User selects the output folder.

# Make a scratch folder
if not os.path.exists(os.path.join(outfolder, "scratch")):
    os.mkdir(os.path.join(outfolder, "scratch"))
             
scratch = os.path.join(outfolder, "scratch")             

# Preliminary environmental settings:
arcpy.env.workspace = nhd
arcpy.env.snapRaster = snap
arcpy.env.extent = snap
arcpy.env.cellSize = 10
arcpy.env.pyramid = "NONE"
arcpy.env.overwriteOutput = "TRUE"
# Projections
nad83 = arcpy.SpatialReference()
nad83.factoryCode = 4269
nad83.create()

albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()

# Make a layer from NHDWaterbody feature class and select out lakes smaller than a hectare. Project to EPSG 102039.
arcpy.MakeFeatureLayer_management("NHDWaterbody","Waterbody", '''"AreaSqKm" >=0.04 AND ("FCode" = 39000 OR\
"FCode" = 39004 OR "FCode" = 39009 OR "FCode" = 39010 OR "FCode" = 39011 OR "FCode" = 39012 OR "FCode" = 43600 OR\
"FCode" = 43613 OR "FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR "FCode" = 43619 OR "FCode" = 43621 OR\
("FCode" = 43601 AND "AreaSqKm" >=0.1 ))''', scratch, "")
arcpy.CopyFeatures_management("Waterbody",os.path.join(scratch, "Waterbody.shp"))
waterbody_nad83 = os.path.join(scratch, "Waterbody.shp")
arcpy.Project_management(waterbody_nad83, os.path.join(scratch, "Waterbody_Albers.shp"), albers, "", nad83)
waterbody_albers = os.path.join(scratch, "Waterbody_Albers.shp")

# Make a shapefile from NHDFlowline and project to EPSG 102039
arcpy.FeatureClassToShapefile_conversion("NHDFlowline", scratch)
flowline_nad83 = os.path.join(scratch, "NHDFlowline.shp")
arcpy.Project_management(flowline_nad83, os.path.join(scratch, "Flowline_Albers.shp"), nad83, "", albers)
flowline_albers = os.path.join(scratch, "Flowline_Albers.shp")

# Add CSI field to flowline_albers and waterbody_albers then calculate unique identifiers for features.
arcpy.AddField_management(flowline_albers, "CSI", "TEXT")
arcpy.CalculateField_management(flowline_albers, "CSI", '''"%s%s" % ("Flowline", !FID!)''', "PYTHON")
arcpy.AddField_management(waterbody_albers, "CSI", "TEXT")
arcpy.CalculateField_management(waterbody_albers, "CSI", '''"%s%s" % ("Waterbody", !FID!)''', "PYTHON")

# Rasterize flowline_albers and waterbody_albers using "CSI" field for the raster's cell value
arcpy.PolylineToRaster_conversion(flowline_albers, "CSI", os.path.join(scratch, "flowline_raster.tif"), "", "", 10)
arcpy.PolygonToRaster_conversion(waterbody_albers, "CSI", os.path.join(scratch, "waterbody_raster.tif"), "", "", 10)
flowline_raster = os.path.join(scratch, "flowline_raster.tif")
waterbody_raster = os.path.join(scratch, "waterbody_raster.tif")

# Switch to scratch workspace
env.workspace = scratch

# Mosaic the rasters together favoring waterbodies over flowlines.
arcpy.MosaicToNewRaster_management("flowline_raster.tif;waterbody_raster.tif", scratch, "seeds_mosaic.tif", albers, "32_BIT_FLOAT", "10", "1", "LAST", "LAST")







             
             




