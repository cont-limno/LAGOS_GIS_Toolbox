# Filename: WallsHU8.py
# Purpose: Creates "walls" of higher elevation on the NED to force conformance to HU8 boundaries.

import os, shutil
import arcpy
from arcpy import env
from arcpy.sa import *


def wall(nhd_gdb, infolder, outfolder, mosaic, height = '100'):

    env.overwriteOutput = True
    env.snapRaster = mosaic
    env.cellSize = mosaic


    albers = arcpy.SpatialReference(102039)
    NAD83 = arcpy.SpatialReference(4269)
    env.outputCoordinateSystem = albers

    env.workspace = nhd_gdb
    nhdsubregion = nhd_gdb[-8:-4]

    # Select only the walls we need
    whereClause = ''' "HUC_8 = '%s' ''' % nhdsubregion
    arcpy.MakeFeatureLayer_management("WBD_HU8", "huc8_layer", whereClause)
    arcpy.CopyFeatures_management("huc8_layer", "HUC8s_in_Subregion")
    wall_lines = arcpy.CreateUniqueName("WallLines")
    arcpy.PolygonToLine_management("HUC8s_in_Subregion", wall_lines)

    arcpy.AddField_management(wall_lines, "WallHeight", "DOUBLE", "", "", "7")
    arcpy.CalculateField_management(wall_lines, "WallHeight", height, "PYTHON")

    # Convert wall lines to raster
    walls = os.path.join(outfolder, "Walls.tif")
    arcpy.FeatureToRaster_conversion(wall_lines, "WallHeight", walls)

    # Add rasters together
    env.workspace = infolder
    env.compression = "NONE"
    rasters = arcpy.ListRasters("NED*fel*") # filled tifs only
    for raster in rasters:
        env.extent = raster
        wallsObject = Raster(walls)
        elevObject = Raster(raster)
        walled_ned = Con(IsNull(wallsObject),elevObject,(wallsObject + elevObject))
        walled_ned.save(os.path.join(outfolder, os.path.basename(raster)))

    arcpy.Delete_management(walls)


def main():
    nhd = arcpy.GetParameterAsText(0) # NHD Subregion file geodatabase
    infolder = arcpy.GetParameterAsText(1) # Folder with filled huc8 clips
    mosaic = arcpy.GetParameterAsText(2)# NED Mosaic for the subregion
    height = arcpy.GetParameterAsText(3) # Wall height in meters
    outfolder = arcpy.GetParameterAsText(4) # Output Folder

    arcpy.CheckOutExtension("Spatial")
    wall(nhd, infolder, outfolder, mosaic, height)
    arcpy.CheckInExtension("Spatial")

def test():
    nhd = 'C:/GISData/Scratch_njs/NHD0109/NHDH0109.gdb'
    infolder = 'C:/GISData/Scratch_njs/PreHPCC/filled_huc8clips0109'
    mosaic = 'C:/GISData/Scratch_njs/PreHPCC/mosaic0109/NED13_0109.tif'
    height = '100'
    outfolder = 'C:/GISData/Scratch_njs/PreHPCC/walled_huc8clips0109'

    arcpy.CheckOutExtension("Spatial")
    wall(nhd, infolder, outfolder, mosaic, height)
    arcpy.CheckInExtension("Spatial")

if __name__ == '__main__':
    main()