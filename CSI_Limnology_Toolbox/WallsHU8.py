# Filename: WallsHU8.py
# Purpose: Creates "walls" of higher elevation on the NED to force conformance to HU8 boundaries.

import os, arcpy, shutil
from arcpy.sa import *

nhd = arcpy.GetParameterAsText(0) # NHD Subregion file geodatabase
infolder = arcpy.GetParameterAsText(1) # Folder with filled huc8 clips
huc6mosaic = arcpy.GetParameterAsText(2)# NED Mosaic for the subregion
hgt = arcpy.GetParameterAsText(3) # Wall height in meters
outfolder = arcpy.GetParameterAsText(4) # Output Folder
def wall():
    arcpy.env.workspace = nhd
    arcpy.env.compression = "NONE"
    arcpy.env.snapRaster = huc6mosaic
    arcpy.env.cellSize = "10"
    albers = arcpy.SpatialReference()
    albers.factoryCode = 102039
    albers.create()

    NAD83 = arcpy.SpatialReference()
    NAD83.factoryCode = "4269"
    NAD83.create()

    arcpy.env.overwriteOutput = "TRUE"
    
    # Project HUC12 and Flowlines to USGS Albers then select the local HUC8s
    arcpy.Project_management("WBD_HU8", "huc8albers", albers, "", NAD83)
    arcpy.CopyFeatures_management("NHDFlowline", "Flowline")
    arcpy.Project_management("Flowline", "flowlinealbers", albers, "", NAD83)
    arcpy.AddMessage("Projected HUC8s and Flowlines to Albers.")

    # Select out Subregion's HUC8s to fc "WBD_HU8_Local"
    arcpy.MakeFeatureLayer_management("huc8albers", "huc8", "", nhd)
    arcpy.MakeFeatureLayer_management("flowlinealbers", "flowline_layer", "", nhd)
    arcpy.SelectLayerByLocation_management("huc8", "INTERSECT", "flowline_layer")
    arcpy.CopyFeatures_management("huc8", "WBD_HU8_Local")
    arcpy.AddMessage("Selected local HUC8s.")

    # Convert to lines and add a field to local HUC8s for wall height
    arcpy.PolygonToLine_management("WBD_HU8_Local","WallLines")
    arcpy.AddField_management("WallLines", "WallHeight", "DOUBLE", "", "", "7")
    arcpy.CalculateField_management("WallLines", "WallHeight", hgt, "PYTHON") 

    # Convert wall lines to raster
    arcpy.FeatureToRaster_conversion("WallLines", "WallHeight", outfolder + "\\" + "Walls.tif")
    walls = os.path.join(outfolder, "Walls.tif")
    subregion_number = os.path.basename(nhd)
    nhdsubregion = subregion_number[4:8]

    # Add rasters together
    arcpy.env.workspace = infolder
    rasters = arcpy.ListRasters("NED*")
    for raster in rasters:
        arcpy.env.extent = raster
        wallsObject = Raster(walls)
        elevObject = Raster(raster)
        walled_ned = Con(IsNull(wallsObject),elevObject,(wallsObject + elevObject))
        walled_ned.save(os.path.join(outfolder, os.path.basename(raster)))

    return                        

wall()
