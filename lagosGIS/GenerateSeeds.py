# Filename: GenerateSeeds.py
# Purpose: Generate seeds for watershed delineation
# from a 24k NHD file geodatabase. Seeds are generated from selected NHDFLowline
# and NHDWaterbody features

import os, re, shutil
import arcpy
from arcpy import env
from arcpy import analysis as AN


def select_pour_points(nhd_gdb, subregion_dem, out_dir, gridcode_table, eligible_lakes_fc,
                        projection = arcpy.SpatialReference(102039)):
    # Preliminary environmental settings:
    env.snapRaster = subregion_dem
    env.extent = subregion_dem
    env.mask = subregion_dem
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
    permid_grid = {r[0]:r[1] for r in arcpy.da.SearchCursor(gridcode_table, ['Permanent_Identifier', 'GridCode'])}
    this_gdb_wbs = permid_grid.keys()
    filter_clause = 'Permanent_Identifier IN ({})'.format(
        ','.join(['\'{}\''.format(id) for id in this_gdb_wbs]))
    eligible_lakes_copy = AN.Select(eligible_lakes_fc, 'eligible_lakes_copy', filter_clause)

    # Make a shapefile from NHDFlowline and project to EPSG 102039
    # 428 = pipeline, 336 = canal; flow direction must be initialized--matches NHDPlus rules pretty well
    flowline_eligible_query = 'FType NOT IN (428,336) OR (FType = 336 and FlowDir = 1)'
    eligible_flowlines = arcpy.Select_analysis(flowline, 'eligible_flowlines', flowline_eligible_query)

    # Add field to flowline_albers and waterbody_albers then calculate unique identifiers for features.
##    # Flowlines get positive values, waterbodies get negative
##    # this will help us to know which is which later
    # Calculate lakes pour_id first, then add maximum to streams pour_ids to get unique ids for all
    arcpy.AddField_management(eligible_lakes_copy, "GridCode", "LONG")
    with arcpy.da.UpdateCursor(eligible_lakes_copy, ['Permanent_Identifier', 'GridCode']) as u_cursor:
        for row in u_cursor:
            u_cursor.updateRow((row[0], permid_grid[row[0]]))

    arcpy.AddField_management(eligible_flowlines, "GridCode", "LONG")
    with arcpy.da.UpdateCursor(eligible_flowlines, ['Permanent_Identifier', 'GridCode']) as u_cursor:
        for row in u_cursor:
            u_cursor.updateRow((row[0], permid_grid[row[0]]))


    # these must be saved as tifs for the mosiac nodata values to work with the watersheds tool
    flowline_raster = os.path.join(pour_dir, "flowline_raster.tif")
    lakes_raster = os.path.join(pour_dir, "lakes_raster.tif")
    arcpy.PolylineToRaster_conversion('eligible_flowlines', "GridCode", flowline_raster, "", "", 10)
    arcpy.PolygonToRaster_conversion(eligible_lakes_copy, "GridCode", lakes_raster, "", "", 10)

    # Mosaic the rasters together favoring waterbodies over flowlines.
    arcpy.MosaicToNewRaster_management([flowline_raster, lakes_raster], pour_dir, "lagos_catseed.tif", projection, "32_BIT_UNSIGNED", "10", "1", "LAST", "LAST")

def main():
    # User inputs parameters:
    nhd_gdb = arcpy.GetParameterAsText(0) # User selects a NHD 24k file geodatabase.
    subregion_dem = arcpy.GetParameterAsText(1) # User selects the corresponding subregion elevation raster.
    out_dir = arcpy.GetParameterAsText(2) # User selects the output folder.
    select_pour_points(nhd_gdb, subregion_dem, out_dir)

def test():
    nhd_gdb = 'C:/GISData/Scratch/NHD0411/NHD0411/NHDH0411.gdb'
    subregion_dem = r'E:\ESRI_FlowDirs\NHD_0411\D8FDR04110001p.tif'
    out_dir = 'C:/GISData/Scratch/NHD0411/NHD0411'
    select_pour_points(nhd_gdb, subregion_dem, out_dir)

if __name__ == '__main__':
    main()








