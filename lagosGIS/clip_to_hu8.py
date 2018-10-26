import os, re
import arcpy
from arcpy import env
from arcpy.sa import *
import csiutils as cu


def clip_to_hu8(raster, nhd_gdb, out_dir,
                    projection = arcpy.SpatialReference(102039)):
    """Outputs a series of rasters, each one clipped to a different HU8. """
    env.workspace = 'in_memory'
    env.outputCoordinateSystem = projection
    env.compression = "NONE" # only final tifs are generated
    env.snapRaster = raster
    env.cellSize = '10'
    env.pyramids = "PYRAMIDS -1 SKIP_FIRST"
    arcpy.CheckOutExtension("Spatial")

    # HUC8 polygons each saved as separate fc inheriting albers from environ
    huc8_fc = os.path.join(nhd_gdb, "WBD_HU8")
    arcpy.MakeFeatureLayer_management(huc8_fc, "huc8_layer")
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

    clips_dir = os.path.join(out_dir, 'huc8clips{0}'.format(huc4_code))
    if not os.path.exists(clips_dir):
        os.mkdir(clips_dir)

##    # add walls
##    arcpy.PolygonToLine_management(huc8_fc, 'wall_lines')
##    arcpy.AddField_management('wall_lines', "height", "DOUBLE")
##    arcpy.CalculateField_management('wall_lines', "height", '500', "PYTHON")
##    arcpy.FeatureToRaster_conversion('wall_lines', "height", 'wall_raster')
##    wallsObject = Raster('wall_raster')
##    elevObject = Raster(raster)
##    walled_ned = Con(IsNull(wallsObject), elevObject,
##                    (wallsObject + elevObject))

    # for each HU8 feature in the fc, make a clip
    with arcpy.da.SearchCursor(huc8_fc, ["HUC_8"]) as cursor:
        for row in cursor:
            if row[0].startswith(huc4_code):
                whereClause = """"{0}" = '{1}'""".format("HUC_8", row[0])
                arcpy.SelectLayerByAttribute_management("huc8_layer", 'NEW_SELECTION', whereClause)
                arcpy.CopyFeatures_management("huc8_layer", "this_hu8")

                # clip the raster
                out_raster = os.path.join(clips_dir, 'NED{0}.tif'.format(row[0]))
                cu.multi_msg('Creating output {0}'.format(out_raster))

                # use a small buffer here because otherwise the walls get
                # cut off in slivers
                arcpy.Buffer_analysis('this_hu8', 'this_hu8_buffer', 5000)
                arcpy.Clip_management(raster, '', out_raster,
                                    'this_hu8_buffer', '#',
                                    'ClippingGeometry')
                arcpy.Delete_management('this_hu8')
                arcpy.Delete_management('this_hu8_buffer')

    arcpy.Delete_management('huc8_layer')
    arcpy.ResetEnvironments()
    arcpy.CheckInExtension("Spatial")


def main():
    burnt_ned = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    out_dir = arcpy.GetParameterAsText(2)
    clip_to_hu8(burnt_ned, nhd_gdb, out_dir)


def test():
    burnt_ned = 'C:/GISData/Scratch/NHD0411/Burnt_0411.tif'
    nhd_gdb = 'C:/GISData/Scratch/NHD0411/NHDH0411.gdb'
    out_dir = 'C:/GISData/Scratch/NHD0411/'
    clip_to_hu8(burnt_ned, nhd_gdb, out_dir)


if __name__ == '__main__':
    main()
