# Filename: cleanwatersheds.py
# Purpose: Interpolate and fill in values for watershed holes.

import os, re
import arcpy
from arcpy import env
from arcpy.sa import *
import csiutils as cu

def create_csi_watersheds(flowdir, pour_dir, nhd_gdb, out_gdb):

    # Starting environmental variables:
    env.extent = flowdir
    env.snapRaster = flowdir
    env.cellSize = 10
    env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    arcpy.CheckOutExtension('Spatial')

    huc8_code = re.search('\d{8}', os.path.basename(flowdir)).group()
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

    # create temp directory because we need shape geometry
    temp_gdb = cu.create_temp_GDB('watersheds' + huc4_code)
    print temp_gdb
    env.workspace = temp_gdb

    wbd_hu8 = os.path.join(nhd_gdb, "WBD_HU8")
    field_name = (arcpy.ListFields(wbd_hu8, "HU*8"))[0].name
    whereClause8 =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc8_code)
    arcpy.Select_analysis(wbd_hu8, "hu8", whereClause8)
    arcpy.Buffer_analysis("hu8", "hu8_buffered", "100 meters")


    # Create the basic watersheds
    pour_points = os.path.join(pour_dir, 'pour_points.tif')
    arcpy.Clip_management(pour_points, '', "pour_points_clipped", "hu8_buffered", '0', 'ClippingGeometry')
    raw_watersheds = os.path.join(out_gdb, 'huc{}_watersheds_precursors'.format(huc8_code))
    cu.multi_msg("Calculating preliminary watersheds...")
    outWatershed = Watershed(flowdir, "pour_points_clipped")
    outWatershed.save(raw_watersheds)


    cu.multi_msg("Clipping watersheds to subregion boundaries and filtering spurious watersheds...")

    # Watershed raster to polygons
    arcpy.RasterToPolygon_conversion(raw_watersheds, "wspoly1", 'NO_SIMPLIFY', "Value")

    # Clip watershed polygons to subregion polys.
    arcpy.Clip_analysis("wspoly1", "hu8", "wsclip1")

    # Clip watershed

##    # Calculate hectares
##    arcpy.AddField_management("wsclip1", "HA", "DOUBLE")
##    arcpy.CalculateField_management("wsclip1", "HA", '''!shape.area@hectares!''', "PYTHON")

    # Create fc of watershed polygons >= 1 ha that coincide with seed lines and polys.
    seedline = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_flowlines')
    seedpoly = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_lakes')
    arcpy.MakeFeatureLayer_management("wsclip1", "wsclip1_lyr")

    arcpy.SelectLayerByLocation_management("wsclip1_lyr", "INTERSECT", seedline, '', "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("wsclip1_lyr", "INTERSECT", seedpoly, '', "ADD_TO_SELECTION")
    arcpy.SelectLayerByAttribute_management("wsclip1_lyr", "SUBSET_SELECTION",'''"Shape_Area" >= 10000''')


    cu.multi_msg("Reshaping watersheds...")
    # Polygon back to raster
    arcpy.PolygonToRaster_conversion("wsclip1_lyr", "grid_code", "ws_legit_ras")
    arcpy.Clip_management("ws_legit_ras", '', "ws_legit_clipped_ras",
                          "hu8", "0", "ClippingGeometry")

    # Make a raster from the subregion (boundary) polygon with zero for cell values.
    arcpy.AddField_management("hu8", "Value", "SHORT")
    arcpy.CalculateField_management("hu8", "Value", "0", "PYTHON")
    arcpy.PolygonToRaster_conversion("hu8", "Value","boundary_raster")
    arcpy.Clip_management("boundary_raster", '', "boundary_raster_clip", "hu8", '', "ClippingGeometry")

    # Fill NoData in watersheds with the zero values from the subregion raster's cells.
    composite = Con(IsNull("ws_legit_clipped_ras"), "boundary_raster_clip", "ws_legit_clipped_ras")
    composite.save("composite_raster")
    arcpy.Clip_management("composite_raster", '', "composite_raster_clip", "hu8", '0', "ClippingGeometry")

    # Make a mask of zero cells. NoData cells are the actual mask for nibble.
    premask = Con(IsNull("composite_raster_clip"), "composite_raster_clip", 0)
    premask.save("premask")

    arcpy.Clip_management("premask",'', "mask", "hu8", '', "ClippingGeometry")

    # Set Null to 1.
    pre_watersheds = Con(IsNull("composite_raster_clip"), 1, "composite_raster_clip")
    pre_watersheds.save("pre_watersheds") # does this speed things up?
##    prews.save("prews.tif")

    # Nibble masked values (null values along boundary).
    cu.multi_msg('Nibbling watersheds as part of reshaping...')
    nibble = Nibble("pre_watersheds", "mask", "DATA_ONLY")
    nibble.save("nibble")
    # Use HU8 buffer so that watersheds will overrun HU8 boundaries and get
    # clipped without weird slivers later
    arcpy.Clip_management("nibble", "", "watersheds_ras", "hu8_buffered", "NoData","ClippingGeometry")

    # Convert watershed raster to polygon.
    # Setting simplify keyword to TRUE in RasterToPolygon_conversion
    # is not working reliably so need to do this in two steps, unfortunately
    cu.multi_msg("Converted reshaped watersheds raster to polygons. If you experience problems with this step, please read Known and Outstanding Bugs.txt")
    arcpy.RasterToPolygon_conversion("watersheds_ras", "nibble_sheds",'SIMPLIFY', "Value") #simplify okay
    cu.multi_msg("test6d")

##    # I'm using 15 as the tolerance
##    # here because the diagonal of a 10x10 pixel is 14.14 m and
##    # I'm okay with a vertex moving as far as it can on the edges of the pixel
##    # This also produces results very similar to using the simplify setting
##    # on RasterToPolygon_conversion, when it works.
##    arcpy.SimplifyPolygon_cartography("nibble_sheds_unsimple",
##        "nibble_sheds_simplify", "POINT_REMOVE", "15 Meters", "0 SquareMeters",
##        "RESOLVE_ERRORS", "NO_KEEP")
    arcpy.Clip_analysis("nibble_sheds", "hu8", "final_watersheds")
    cu.multi_msg("test7")

    # Join Permanent ID from Waterbody seed shapefile
    final_watersheds_out = os.path.join(out_gdb, 'huc{}_final_watersheds'.format(huc8_code))
    arcpy.JoinField_management("final_watersheds", 'grid_code', seedpoly, 'POUR_ID', ['Permanent_Identifier'])
    cu.multi_msg("test9")

    # this block bumps out sheds so that they fully contain their own lakes
    # sometimes a little bit of another shed is overlapping the lake simply
    # due to the raster/polygon differences
    # 1) delete fields so watersheds and seedpoly share schema
    # 2) update features, keeping borders
    # 3) instead of lots of nulls make unique dissolve_id for all so that nulls aren't dissolved into one
    # 4) dissolve features on dissolve_id keeping the Permanent_Identifier field
    arcpy.CopyFeatures_management(seedpoly, 'lakes_nofields')
    for fc in ['lakes_nofields', 'final_watersheds']:
        fields = arcpy.ListFields(fc)
        for f in fields:
            if f != 'Permanent_Identifier':
                try:
                    arcpy.DeleteField_management(fc, f)
                except:
                    continue
    cu.multi_msg("test10")
    arcpy.Update_analysis("final_watersheds", 'lakes_nofields', 'update_fc')
    arcpy.AddField_management('update_fc', 'dissolve_id', 'TEXT', 255)
    arcpy.MakeFeatureLayer_management('update_fc', 'update_lyr')
    arcpy.SelectLayerByAttribute_management('update_lyr', 'NEW_SELECTION', """"Permanent_Identifier" is not null""")
    cu.multi_msg("test11")
    arcpy.CalculateField_management('update_lyr', 'dissolve_id', '!Permanent_Identifier!', 'PYTHON')
    arcpy.SelectLayerByAttribute_management('update_lyr', 'SWITCH_SELECTION')
    arcpy.CalculateField_management('update_lyr', 'dissolve_id', '!OBJECTID!', 'PYTHON')
    arcpy.SelectLayerByAttribute_management('update_lyr', 'CLEAR_SELECTION')
    arcpy.Dissolve_management('update_lyr', "final_watersheds_bumped", 'dissolve_id', 'Permanent_Identifier FIRST')
    cu.rename_field("final_watersheds_bumped", "FIRST_Permanent_Identifier", "Permanent_Identifier", deleteOld = True)
    cu.multi_msg("test12")
    arcpy.DeleteField_management('final_watersheds_bumped', 'dissolve_id')

    arcpy.CopyFeatures_management("final_watersheds_bumped", final_watersheds_out)

    temp_items = arcpy.ListRasters() + arcpy.ListFeatureClasses() + [temp_gdb]
    for item in temp_items:
        try:
            arcpy.Delete_management(item)
        except:
            continue

    arcpy.ResetEnvironments()
    arcpy.CheckInExtension('Spatial')
    cu.multi_msg("Complete.")


def main():
    flowdir = arcpy.GetParameterAsText(0)
    pour_dir = arcpy.GetParameterAsText(1)
    nhd_gdb = arcpy.GetParameterAsText(2)
    out_gdb = arcpy.GetParameterAsText(3)
    create_csi_watersheds(flowdir, pour_dir, nhd_gdb, out_gdb)

def test():
    flowdir = r'E:\ESRI_FlowDirs\NHD_0802\D8FDR08020203p.tif'
    pour_dir = r'C:\GISData\Scratch\new_pourpoints\pourpoints0802'
    nhd_gdb = r'E:\nhd\fgdb\NHDH0802.gdb'
    out_gdb = r'C:\GISData\Scratch\Scratch.gdb'
    create_csi_watersheds(flowdir, pour_dir, nhd_gdb, out_gdb)


def test2():
    flowdir = r'E:\ESRI_FlowDirs\NHD_0411\D8FDR04110004p.tif'
    pour_dir = r'C:\GISData\Scratch\new_pourpoints\pourpoints0411'
    nhd_gdb = r'E:\nhd\fgdb\NHDH0411.gdb'
    out_gdb = r'C:\GISData\Scratch\Scratch.gdb'
    create_csi_watersheds(flowdir, pour_dir, nhd_gdb, out_gdb)

if __name__ == '__main__':
    main()









