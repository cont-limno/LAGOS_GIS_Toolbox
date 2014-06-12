import os, re
import arcpy
from arcpy import env
import csiutils as cu

def clip_to_hu8(raster, nhd_gdb, out_dir,
        projection = arcpy.SpatialReference(102039)):
    """Outputs a series of rasters, each one clipped to a different HU8. """
    env.workspace = nhd_gdb
    env.outputCoordinateSystem = projection
    env.compression = "NONE" # only final tifs are generated

    # HUC8 polygons each saved as separate fc inheriting albers from environ
    huc8_fc = "WBD_HU8"
    arcpy.MakeFeatureLayer_management(huc8_fc, "huc8_layer")
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

    clips_dir = os.path.join(out_dir, 'huc8clips{0}'.format(huc4_code))
    if not os.path.exists(clips_dir):
        os.mkdir(clips_dir)

    with arcpy.da.SearchCursor(huc8_fc, ["HUC_8"]) as cursor:
        for row in cursor:
            if row[0].startswith(huc4_code):
                whereClause = """"{0}" = '{1}'""".format("HUC_8", row[0])
                arcpy.SelectLayerByAttribute_management("huc8_layer", 'NEW_SELECTION', whereClause)
                arcpy.CopyFeatures_management("huc8_layer", "in_memory/fc")
                out_raster = os.path.join(clips_dir, 'NED{0}.tif'.format(row[0]))

                # instead of the unnecessary 5km buffer and walling process
                # just going to clip directly to HU8 boundary and set everything
                # outside HIGHER than any possible elevation value
                # the point is that flow isn't allowed to cross HU8s, right?
                # since flowdir calcs are per HU8 anyway
                # TEST new flowdir outputs against old before keeping this
                cu.multi_msg('Creating output {0}'.format(out_raster))
                arcpy.Clip_management(raster, '', out_raster,
                                    'in_memory/fc', '100000',
                                    'ClippingGeometry')
                arcpy.Delete_management('in_memory/fc')

##    #retrieve only the single huc8 fcs and not the one with all of them
##    fcs = arcpy.ListFeatureClasses("HUC%s*" % huc4_code, "Polygon", out_feature_dataset)
##    fcs_buffered = [os.path.join(out_feature_dataset, fc + "_buffer") for fc in fcs]
##    out_clips = [os.path.join(outfolder, "huc8clips" + huc4_code,
##    "NED" + fc[3:] + ".tif") for fc in fcs]
##
##    # Buffer HUC8 feature classes by 5000m
##    for fc, fc_buffered in zip(fcs, fcs_buffered):
##        arcpy.Buffer_analysis(fc, fc_buffered, "5000 meters")
##
##    cu.multi_msg("Created HUC8 buffers.")
##    arcpy.RefreshCatalog(nhd)

##    # Clips rasters
##    cu.multi_msg("Starting HUC8 clips...")
##    for fc_buffered, out_clip in zip(fcs_buffered, out_clips):
##        arcpy.Clip_management(raster, '', out_clip, fc_buffered, "0", "ClippingGeometry")
##
##    arcpy.Compact_management(nhd)
##
##    cu.multi_msg("Clipping complete.")


def main():
    pass

def test():
    burnt_ned = 'C:/GISData/Scratch/Burnt_0411.tif'
    nhd_gdb = 'C:/GISData/Scratch/NHD0411/NHDH0411.gdb'
    out_dir = 'C:/GISData/Scratch/NHD0411/'
    clip_to_hu8(burnt_ned, nhd_gdb, out_dir)


if __name__ == '__main__':
    main()
