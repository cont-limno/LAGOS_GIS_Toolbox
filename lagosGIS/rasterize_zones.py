# Converts multiple polygon feature classes to "zone" rasters using a common grid
import math
import os
import arcpy
from arcpy import env
this_files_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_files_dir)
SNAP_RASTER = '../common_grid.tif'
CELL_SIZE = 90

def multi_convert_to_raster(polygon_fc_list, output_workspace):

    for polygon_fc in polygon_fc_list:
        if 'hu12' in polygon_fc or 'buff' in polygon_fc or ('ws' in polygon_fc and 'nws' not in polygon_fc):
            cell_size = 30
        else:
            cell_size = CELL_SIZE

        env.extent = polygon_fc
        env.snapRaster = SNAP_RASTER
        short_name = os.path.splitext(os.path.basename(polygon_fc))[0]
        arcpy.AddMessage("Converting {}...".format(short_name))
        output_raster = os.path.join(output_workspace, short_name + '_raster')
        zoneid_field = arcpy.ListFields(polygon_fc, '*zoneid')[0].name
        output_raster = arcpy.PolygonToRaster_conversion(polygon_fc,
                                         zoneid_field,
                                         output_raster,
                                         'CELL_CENTER',
                                         cellsize = cell_size)
        arcpy.BuildPyramids_management(output_raster, SKIP_FIRST = True)
    arcpy.AddMessage("Completed.")

def main():
    polygon_fc_input = arcpy.GetParameterAsText(0)
    polygon_fc_list = polygon_fc_input.split(";")
    output_workspace = arcpy.GetParameterAsText(1)
    multi_convert_to_raster(polygon_fc_list, output_workspace)

if __name__ == '__main__':
    main()
