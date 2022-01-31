import os
import arcpy
import zonal_summary_of_raster_data

def wrapper(lagos_zone_rasters_list, raster, variable_basename = '', is_thematic=False):
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

