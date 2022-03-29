# filename: rasterize_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)


import os
import arcpy
from arcpy import env
this_files_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_files_dir)
SNAP_RASTER = '../common_grid.tif'
CELL_SIZE = 90


def rasterize(polygon_fc_list, output_workspace):
    """
    Converts zone polygons in a spatial division dataset to a classed raster dataset with one class per unique zone
    polygon using a common standard for cell size and cell centers.
    :param polygon_fc_list: List of one or more polygon feature classes representing zones (spatial divisions)
    :param output_workspace: Output file geodatabase to save the output Raster datasets to
    :return: None
    """

    for polygon_fc in polygon_fc_list:
        # Choose 30m for spatial divisions with smaller average feature size (hu12, buff100, buff500, nws)
        # Choose 90m for spatial divisions larger than about the average County size
        # 90m is enough to get mean raster stats for zone with necessary precision
        if 'hu12' in polygon_fc or 'buff' in polygon_fc or ('ws' in polygon_fc and 'nws' not in polygon_fc):
            cell_size = 30
        else:
            cell_size = CELL_SIZE

        # Set up raster processing environments to control output and make names
        env.extent = polygon_fc
        env.snapRaster = SNAP_RASTER
        short_name = os.path.splitext(os.path.basename(polygon_fc))[0]
        arcpy.AddMessage("Converting {}...".format(short_name))
        output_raster = os.path.join(output_workspace, short_name + '_raster')
        zoneid_field = arcpy.ListFields(polygon_fc, '*zoneid')[0].name

        # Convert the polygons to raster and build pyramids with first level missing to save space
        output_raster = arcpy.PolygonToRaster_conversion(polygon_fc,
                                                         zoneid_field,
                                                         output_raster,
                                                         'CELL_CENTER',
                                                         cellsize = cell_size)
        arcpy.BuildPyramids_management(output_raster, SKIP_FIRST=True)


def main():
    polygon_fc_input = arcpy.GetParameterAsText(0)
    polygon_fc_list = polygon_fc_input.split(";")
    output_workspace = arcpy.GetParameterAsText(1)
    rasterize(polygon_fc_list, output_workspace)


if __name__ == '__main__':
    main()
