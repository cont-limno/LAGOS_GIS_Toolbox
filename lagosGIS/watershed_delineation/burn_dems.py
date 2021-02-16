# filename: burn_dems.py
# author: Scott Stopyak, Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy
from arcpy.sa import *
from arcpy import env
from NHDNetwork import NHDNetwork


def burn_streams_and_sinks(subregion_ned, nhd_gdb, burnt_out,
                projection = arcpy.SpatialReference(102039)):
    """
    Enforce stream linework in hydrologic conditioning of DEM and add walls at the HU12 boundaries.
    :param subregion_ned: A mosaicked (NED) DEM covering the subregion being processed with elevation in cm
    :param nhd_gdb: The NHD HR subregion geodatabase being processed
    :param burnt_out: Path of the output raster with burned streams
    :param projection: Optional, default is USGS Albers (102039)
    :return: Raster object with burned streams
    """

    env.snapRaster = subregion_ned
    env.outputCoordinateSystem = projection
    env.compression = "LZ77" # compress temp tifs for speed
    env.extent = subregion_ned
    env.workspace = 'in_memory'

    burnline = os.path.join(nhd_gdb, 'NHDBurnLineEvent')
    if not arcpy.Exists(burnline):
        burnline = os.path.join(nhd_gdb, 'NHDFlowline')

    nhdarea = os.path.join(nhd_gdb, 'NHDArea')
    nhdwaterbody = os.path.join(nhd_gdb, 'NHDWaterbody')

    # Copy flowlines to shapefile that will inherit environ output coord system
    # just easier to have a copy in the correct projection later

    # 428 = pipeline, 336 = canal, flow direction must be initialized--matches NHDPlus rules pretty well
    # will have no effect if using burnline layer
    flowline_eligible_query = 'FType NOT IN (428,336) OR (FType = 336 and FlowDir = 1)'
    flowline_burn = arcpy.Select_analysis(burnline, 'flowline_proj', flowline_eligible_query)
    area_burn = arcpy.Select_analysis(nhdarea, 'area_burn', 'FType = 460') # StreamRiver only
    waterbody_burn = arcpy.Select_analysis(nhdwaterbody, 'waterbody_burn', 'FType IN (390, 436)')

    # identify valid sinks
    network = NHDNetwork(nhd_gdb)
    waterbody_ids = network.define_lakes(strict_minsize=False, force_lagos=True).keys()
    arcpy.AddMessage("Identifying sink lakes...")
    lake_conn_classes = {id:network.classify_waterbody_connectivity(id) for id in waterbody_ids}
    sink_lake_ids = [k for k,v in lake_conn_classes.items() if v in ('Isolated', 'TerminalLk', 'Terminal')]
    sink_lakes_query = 'Permanent_Identifier IN ({})'.format(
        ','.join(['\'{}\''.format(id) for id in sink_lake_ids]))
    sink_lakes = arcpy.Select_analysis(network.waterbody, 'sink_lakes', sink_lakes_query)

    # protect these sink lakes in DEM
    sink_centroids = arcpy.FeatureToPoint_management(sink_lakes, 'sink_centroids', 'INSIDE')
    sink_centroids_raster = arcpy.PointToRaster_conversion(sink_centroids, "OBJECTID", "centroids_raster", cellsize=10)

    # Feature to Raster- rasterize the feature classes
    # will inherit grid from env.snapRaster
    flowline_raster = arcpy.FeatureToRaster_conversion(flowline_burn, "OBJECTID",
                                    'flowline_raster', "10")
    nhdarea_raster = arcpy.FeatureToRaster_conversion(area_burn, "OBJECTID",
                                     'nhdarea_raster', "10")
    lakes_raster = arcpy.FeatureToRaster_conversion(waterbody_burn, "OBJECTID",
                                                      'lakes_raster', "10")

    arcpy.AddMessage("Converted feature classes to raster.")

    # Raster Calculator- burns in streams, beveling in from 500m
    arcpy.AddMessage("Burning streams into raster...")
    arcpy.CheckOutExtension("Spatial")

    # HU12 layer
    huc12_fc = os.path.join(nhd_gdb, "WBDHU12")
    arcpy.MakeFeatureLayer_management(huc12_fc, "huc12_layer")

    # make the walls raster object
    wall_lines = arcpy.PolygonToLine_management(huc12_fc, 'wall_lines')
    arcpy.AddField_management(wall_lines, "height", "FLOAT")
    wall_ht = 500000
    arcpy.CalculateField_management(wall_lines, "height", '{}'.format(wall_ht), "PYTHON")
    arcpy.FeatureToRaster_conversion(wall_lines, "height", 'wall_raster')
    walls = Raster('wall_raster')

    # convert heights to cm and round to 1 mm, to match NHDPlus
    distance = EucDistance(flowline_burn, cell_size = "10")
    streams = Reclassify(Raster(flowline_raster) > 0, "Value", "1 1; NoData 0")
    banks = Reclassify(Raster(nhdarea_raster) > 0, "Value", "1 1; NoData 0")
    lakes = Reclassify(Raster(lakes_raster) > 0, "Value", "1 1; NoData 0")
    sinks = Reclassify(Raster(sink_centroids_raster) > 0, "Value", "1 1; NoData 0")

    width = 60 # in horizontal map units
    soft_drop = 5000 # cm
    sharp_drop = 100000 # cm
    areal_drop = 10000 # cm
    burnt = Raster(subregion_ned) \
            - (sharp_drop * streams) \
            - (areal_drop * banks) \
            - (areal_drop * lakes) \
            + soft_drop * ((distance/width) - 1) * (distance < width) # beveled drop, convert distance to cm
    burnt_with_sinks = SetNull(sinks, burnt)
    no_wall = BooleanOr(IsNull(walls), streams) # allow streams to cut walls
    walled = Con(no_wall, burnt_with_sinks, (burnt_with_sinks + walls))

    arcpy.AddMessage("Saving output raster...")
    walled.save('in_memory/walled_save')
    arcpy.CopyRaster_management('in_memory/walled_save', burnt_out) # 2 steps in order to use raster compression


    # Delete intermediate rasters and shapefiles
    for item in [flowline_burn, area_burn, waterbody_burn,
                 sink_lakes, sink_centroids, sink_centroids_raster,
                 flowline_raster, nhdarea_raster, lakes_raster, 'huc12_layer',
                 wall_lines, 'walled_save']:
      arcpy.Delete_management(item)
    arcpy.CheckInExtension("Spatial")
    arcpy.ResetEnvironments()
    return burnt_out


def main():
    subregion_ned = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    burnt_out = arcpy.GetParameterAsText(2)
    burn_streams(subregion_ned, nhd_gdb, burnt_out)


if __name__ == "__main__":
    main()