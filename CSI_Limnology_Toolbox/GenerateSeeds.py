# Filename: GenerateSeeds.py
# Purpose: Generate seeds for watershed delineation
# from a 24k NHD file geodatabase. Seeds are generated from selected NHDFLowline
# and NHDWaterbody features

import os, re, shutil
import arcpy
from arcpy import env

def select_pour_points(nhd_gdb, subregion_dem, out_dir,
                        projection = arcpy.SpatialReference(102039)):
    # Preliminary environmental settings:
    env.snapRaster = subregion_dem
    env.extent = subregion_dem
    env.cellSize = 10
    env.pyramid = "PYRAMIDS -1 SKIP_FIRST"
    env.outputCoordinateSystem = projection
    arcpy.CheckOutExtension("Spatial")

    waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    flowline = os.path.join(nhd_gdb, 'NHDFlowline')

    # Make a folder for the pour points
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()
    pour_dir = os.path.join(out_dir, 'pourpoints{0}'.format(huc4_code))
    pour_gdb = os.path.join(pour_dir, 'pourpoints.gdb')
    if not os.path.exists(pour_dir):
        os.mkdir(pour_dir)
    if not arcpy.Exists(pour_gdb):
        arcpy.CreateFileGDB_management(pour_dir, 'pourpoints.gdb')

    env.workspace = pour_gdb

    # Make a layer from NHDWaterbody feature class and select out lakes smaller than a hectare. Project to EPSG 102039.
    fcodes = (39000, 39004, 39009, 39010, 39011, 39012, 43600, 43613, 43615, 43617, 43618, 43619, 43621)
    where_clause = '''("AreaSqKm" >=0.04 AND "FCode" IN %s) OR ("FCode" = 43601 AND "AreaSqKm" >= 0.1)''' % (fcodes,)

    arcpy.Select_analysis(waterbody, 'eligible_lakes', where_clause)

    # Make a shapefile from NHDFlowline and project to EPSG 102039
    arcpy.CopyFeatures_management(flowline, 'eligible_flowlines')

    # Add field to flowline_albers and waterbody_albers then calculate unique identifiers for features.
    # Flowlines get positive values, waterbodies get negative
    # this will help us to know which is which later
    arcpy.AddField_management('eligible_flowlines', "POUR_ID", "LONG")
    arcpy.CalculateField_management('eligible_flowlines', "POUR_ID", '!OBJECTID!', "PYTHON")
    arcpy.AddField_management('eligible_lakes', "POUR_ID", "TEXT")
    arcpy.CalculateField_management('eligible_lakes', "POUR_ID", '!OBJECTID! * -1', "PYTHON")

    flowline_raster = "flowline_raster"
    lakes_raster = "lakes_raster"
    arcpy.PolylineToRaster_conversion('eligible_flowlines', "POUR_ID", flowline_raster, "", "", 10)
    arcpy.PolygonToRaster_conversion('eligible_lakes', "POUR_ID", lakes_raster, "", "", 10)

    # Mosaic the rasters together favoring waterbodies over flowlines.
    arcpy.MosaicToNewRaster_management([flowline_raster, lakes_raster],
                pour_dir, "pour_points.tif", projection, "32_BIT_SIGNED",
                "10", "1", "LAST", "LAST")

def main():
    # User inputs parameters:
    nhd_gdb = arcpy.GetParameterAsText(0) # User selects a NHD 24k file geodatabase.
    subregion_dem = arcpy.GetParameterAsText(1) # User selects the corresponding subregion elevation raster.
    out_dir = arcpy.GetParameterAsText(2) # User selects the output folder.
    select_pour_points(nhd_gdb, subregion_dem, out_dir)

def test():
    nhd_gdb = 'C:/GISData/Scratch/NHD0411/NHDH0411.gdb'
    subregion_dem = 'C:/GISData/Scratch/NHD0411/NED13_0411.tif'
    out_dir = 'C:/GISData/Scratch/NHD0411'
    select_pour_points(nhd_gdb, subregion_dem, out_dir)









