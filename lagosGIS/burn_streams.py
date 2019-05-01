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
    # Copy flowlines to shapefile that will inherit environ output coord system
    # just easier to have a copy in the correct projection later
    arcpy.CopyFeatures_management(flowline, 'flowline_proj')

    # Feature to Raster- rasterize the NHDFlowline
    # will inherit grid from env.snapRaster
    arcpy.FeatureToRaster_conversion('flowline_proj', "OBJECTID",
                                    'flowline_raster', "10")
    arcpy.AddMessage("Converted flowlines to raster.")

    # Raster Calculator- burns in streams, beveling in from 500m
    arcpy.AddMessage("Burning streams into raster...")
    arcpy.CheckOutExtension("Spatial")

    # convert heights to cm and round to 1 mm, to match NHDPlus
    distance = EucDistance('flowline_proj', cell_size = "10")
    streams = Reclassify(Raster('flowline_raster') > 0, "Value", "1 1; NoData 0")
    width = 16000
    soft = 50000
    sharp = 100000
    burnt = round(
        100 * Raster(subregion_ned)- (sharp * streams) - (1/soft * (soft - distance) * int(distance < width)),
        1)

    arcpy.AddMessage("Saving output raster...")
    burnt.save(burnt_out)

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