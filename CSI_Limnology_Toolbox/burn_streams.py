import arcpy
from arcpy.sa import *
from arcpy import env
import csiutils as cu

def burn_streams(subregion_ned, nhd_gdb, burnt_out,
                projection = arcpy.SpatialReference(102039)):
    env.snapRaster = subregion_ned
    env.outputCoordinateSystem = projection
    env.compression = "LZ77" # compress temp tifs for speed
    env.workspace = nhd_gdb

    # Copy flowlines to shapefile that will inherit environ output coord system
    # just easier to have a copy in the correct projection later
    flow_line = "in_memory/NHDFlowline_Projected"
    arcpy.CopyFeatures_management("NHDFlowline", flow_line)
##    arcpy.FeatureClassToFeatureClass_conversion("NHDFlowline", "in_memory", flow_line)

    cu.multi_msg("Prepared NHDFlowline for rasterizing.")

    # Feature to Raster- rasterize the NHDFlowline
    flow_line_raster = "in_memory/flow_line_raster"

    # will inherit grid from env.snapRaster
    arcpy.FeatureToRaster_conversion("NHDFlowline", "OBJECTID",
                                    flow_line_raster, "10")
    cu.multi_msg("Converted flowlines to raster.")

    # Raster Calculator- burns in streams, beveling in from 500m
    cu.multi_msg("Burning streams into raster, 10m deep and beveling in from 500m out. This may take a while....")
    arcpy.CheckOutExtension("Spatial")
    distance = EucDistance(flow_line, cell_size = "10")
    streams = Reclassify(Raster(flow_line_raster) > 0, "Value", "1 1; NoData 0")
    burnt = Raster(subregion_ned) - (10 * streams) - (0.02 * (500 - distance) * (distance < 500))

    cu.multi_msg("Saving output raster...")
    burnt.save(burnt_out)

    # Delete intermediate rasters and shapefiles
    for item in [flow_line, flow_line_raster]:
        arcpy.Delete_management(item)
    arcpy.CheckInExtension("Spatial")
    cu.multi_msg("Burn process completed")


def main():
    subregion_ned = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    burnt_out = arcpy.GetParameterAsText(2)
    burn_streams(subregion_ned, nhd_gdb, burnt_out)

def test():
    subregion_ned = 'C:/GISData/Scratch/NHD0411/NED13_0411.tif'
    nhd_gdb = 'C:/GISData/Scratch/NHD0411/NHDH0411.gdb'
    burnt_out = 'C:/GISData/Scratch/Burnt_0411.tif'
    burn_streams(subregion_ned, nhd_gdb, burnt_out)

if __name__ == "__main__":
    main()