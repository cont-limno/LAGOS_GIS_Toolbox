# filename: flow_direction_toolbox.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import nhd_plus_watersheds_tools as npwt

hydrodem_raster = arcpy.GetParameterAsText(0)
nhd_fdr = arcpy.GetParameterAsText(1)
flow_direction_raster_out = arcpy.GetParameterAsText(2)

npwt.flow_direction(hydrodem_raster, nhd_fdr, flow_direction_raster_out)