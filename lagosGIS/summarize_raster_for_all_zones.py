# filename: summarize_raster_for_all_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)
# status: To be implemented

import os
import arcpy
import zonal_summary_of_raster_data

def summarize(lagos_zone_rasters_list, raster_to_summarize, variable_basename = '', is_thematic=False):
    """
    This is the "magic button" function that calculates statistics at multiple scales for a value raster of interest.
    This wrapper function also serves to do some name management in conformance with the design of the LAGOS database
    creation workflow.
    :param lagos_zone_rasters_list:
    :param raster:
    :param variable_basename:
    :param is_thematic:
    :return:
    """
    # manage the call

    # manage the renaming process

def main():
    lagos_zone_raster_list_input = arcpy.GetParameterAsText(0)
    lagos_zone_raster_list = lagos_zone_raster_list_input.split(";")
    raster_to_summarize = arcpy.GetParameterAsText(1)
    variable_basename = arcpy.GetParameterAsText(2)
    is_thematic = arcpy.GetParameter(3) # boolean
    summarize(lagos_zone_raster_list, raster_to_summarize, variable_basename, is_thematic)

if __name__ == '__main__':
    main()