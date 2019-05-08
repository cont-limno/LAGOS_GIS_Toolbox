import os
import arcpy
from arcpy.sa import *
from arcpy import env
import csiutils as cu

def burn_streams(subregion_ned, nhd_gdb, burnt_out,
                projection = arcpy.SpatialReference(102039)):
    env.snapRaster = subregion_ned
    env.outputCoordinateSystem = projection
    env.compression = "LZ77" # compress temp tifs for speed
    env.extent = subregion_ned
    env.workspace = 'in_memory'

    flowline = os.path.join(nhd_gdb, 'NHDFlowline')
    nhdarea = os.path.join(nhd_gdb, 'NHDArea')

    # Copy flowlines to shapefile that will inherit environ output coord system
    # just easier to have a copy in the correct projection later

    # 428 = pipeline, 336 = canal, flow direction must be initialized--matches NHDPlus rules pretty well
    flowline_eligible_query = 'FType NOT IN (428,336) OR (FType = 336 and FlowDir = 1)'
    arcpy.Select_analysis(flowline, 'flowline_proj', flowline_eligible_query)

    # Feature to Raster- rasterize the feature classes
    # will inherit grid from env.snapRaster
    flowline_raster = arcpy.FeatureToRaster_conversion('flowline_proj', "OBJECTID",
                                    'flowline_raster', "10")
    nhdarea_raster = arcpy.FeatureToRaster_conversion(nhdarea, "OBJECTID",
                                     'nhdarea_raster', "10")

    arcpy.AddMessage("Converted feature classes to raster.")

    # Raster Calculator- burns in streams, beveling in from 500m
    arcpy.AddMessage("Burning streams into raster...")
    arcpy.CheckOutExtension("Spatial")

    # HU12 layer
    huc12_fc = os.path.join(nhd_gdb, "WBDHU12")
    arcpy.MakeFeatureLayer_management(huc12_fc, "huc12_layer")

    # make the walls raster object
    arcpy.PolygonToLine_management(huc12_fc, 'wall_lines')
    arcpy.AddField_management('wall_lines', "height", "FLOAT")
    wall_ht = 500000
    arcpy.CalculateField_management('wall_lines', "height", '{}'.format(wall_ht), "PYTHON")
    arcpy.FeatureToRaster_conversion('wall_lines', "height", 'wall_raster')
    walls = Raster('wall_raster')

    # convert heights to cm and round to 1 mm, to match NHDPlus
    distance = EucDistance('flowline_proj', cell_size = "10")
    streams = Reclassify(Raster('flowline_raster') > 0, "Value", "1 1; NoData 0")
    banks = Reclassify(Raster('nhdarea_raster') > 0, "Value", "1 1; NoData 0")

    width = 6000
    soft_drop = 50000
    sharp_drop = 500000
    areal_drop = 10000
    burnt = 100 * Raster(subregion_ned) \
            - (sharp_drop * streams) \
            - (areal_drop * banks) \
            - (1/soft_drop * (soft_drop - distance) * distance < width)
    no_wall = BooleanOr(IsNull(walls), streams) # allow streams to cut walls
    walled = Con(no_wall, burnt, walls)

    arcpy.AddMessage("Saving output raster...")
    walled.save(burnt_out)

    # Delete intermediate rasters and shapefiles
    for item in ['flowline_proj', 'flowline_raster']:
        arcpy.Delete_management(item)
    arcpy.CheckInExtension("Spatial")
    arcpy.AddMessage("Burn process completed")
    arcpy.ResetEnvironments()
    return burnt_out

def main():
    subregion_ned = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    burnt_out = arcpy.GetParameterAsText(2)
    burn_streams(subregion_ned, nhd_gdb, burnt_out)

if __name__ == "__main__":
    main()