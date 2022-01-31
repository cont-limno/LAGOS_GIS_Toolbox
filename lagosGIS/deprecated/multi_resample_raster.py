# Converts multiple rasters to use the common grid that matches the zone rasters and have a common suffix
# Saves the new raster in the same location as the old one
# common suffix is LAGOS30m
import os
import arcpy
from arcpy import env
this_files_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_files_dir)
SNAP_RASTER = '../common_grid.tif'
CELL_SIZE = 30

def multi_convert_to_raster(raster_list):
    for raster in raster_list:
        env.extent = raster
        env.snapRaster = SNAP_RASTER
        arcpy.AddMessage("Converting {}...".format(raster))
        output_raster = '{}_LAGOS30m{}'.format(os.path.splitext(raster)[0], os.path.splitext(raster)[1])
        arcpy.Resample_management()
        arcpy.PolygonToRaster_conversion(polygon_fc,
                                         zone_field,
                                         output_raster,
                                         'CELL_CENTER',
                                         cellsize = CELL_SIZE)
        arcpy.BuildPyramids_management(output_raster, SKIP_FIRST = True)
    arcpy.AddMessage("Completed.")

def main():
    polygon_fc_input = arcpy.GetParameterAsText(0)
    polygon_fc_list = polygon_fc_input.split(";")
    output_workspace = arcpy.GetParameterAsText(1)
    multi_convert_to_raster(polygon_fc_list, output_workspace)

if __name__ == '__main__':
    main()
