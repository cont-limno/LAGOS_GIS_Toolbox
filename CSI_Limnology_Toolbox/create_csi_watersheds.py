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

    # Create a scratch folder and set as current workspace.
    huc8_code = re.search('\d{8}', os.path.basename(flowdir)).group()
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

    # create temp directory because we need shape geometry
    temp_gdb = cu.create_temp_GDB('watersheds' + huc4_code)
    env.workspace = temp_gdb

    # Extract the subregion polygon
    wbd_hu4 = os.path.join(nhd_gdb, "WBD_HU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    arcpy.Select_analysis(wbd_hu4, "wbd_poly", whereClause)


    # Create the basic watersheds
    pour_points = os.path.join(pour_dir, 'pour_points.tif')
    raw_watersheds = os.path.join(out_gdb, 'huc{}_watersheds_precursors'.format(huc8_code))
    cu.multi_msg("Calculating preliminary watersheds...")
    outWatershed = Watershed(flowdir, pour_points)
    outWatershed.save(raw_watersheds)


    cu.multi_msg("Clipping watersheds to subregion boundaries and filtering spurious watersheds...")

    # Watershed raster to polygons
    arcpy.RasterToPolygon_conversion(raw_watersheds, "wspoly1", 'NO_SIMPLIFY', "Value")

    # Clip watershed polygons to subregion polys.
    arcpy.Clip_analysis("wspoly1", "wbd_poly", "wsclip1")

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
                          "wbd_poly", "0", "ClippingGeometry")

    # Make a raster from the subregion (boundary) polygon with zero for cell values.
    arcpy.AddField_management("wbd_poly", "Value", "SHORT")
    arcpy.CalculateField_management("wbd_poly", "Value", "0", "PYTHON")

    arcpy.PolygonToRaster_conversion("wbd_poly", "Value","boundary_raster")
    arcpy.Clip_management("boundary_raster", '', "boundary_raster_clip", "wbd_poly", '', "ClippingGeometry")

    # Fill NoData in watersheds with the zero values from the subregion raster's cells.
    composite = Con(IsNull("ws_legit_clipped_ras"), "boundary_raster_clip", "ws_legit_clipped_ras")
    composite.save("composite_raster")
    arcpy.Clip_management("composite_raster", '', "composite_raster_clip", "wbd_poly", '0', "ClippingGeometry")

    # Make a mask of zero cells. NoData cells are the actual mask for nibble.
    premask = Con(IsNull("composite_raster_clip"), "composite_raster_clip", 0)
    premask.save("premask")

    arcpy.Clip_management("premask",'', "mask", "wbd_poly", '', "ClippingGeometry")

    # Set Null to 1.
    pre_watersheds = Con(IsNull("composite_raster_clip"), 1, "composite_raster_clip")
##    prews.save("prews.tif")

    # Nibble masked values (null values along boundary).
    nibble = Nibble(pre_watersheds, "mask", "DATA_ONLY")
    nibble.save("nibble")

    arcpy.Buffer_analysis("wbd_poly", "subregion_buffer", "100 meters")
    arcpy.Clip_management("nibble", "", "watersheds_ras", "subregion_buffer", "NoData","ClippingGeometry")

    # Convert watershed raster to polygon.
    arcpy.RasterToPolygon_conversion("watersheds_ras", "rawwatersheds",'', "Value")
    arcpy.Clip_analysis("rawwatersheds", "wbd_poly", "final_watersheds")

    # Add and calculate a new text join field.
    arcpy.AddField_management("final_watersheds", "JOIN", "TEXT")
    arcpy.CalculateField_management("final_watersheds", "JOIN", '''!grid_code! - 1''', "PYTHON")

    # Join Permanent ID from Waterbody seed shapefile
    final_watersheds_out = os.path.join(out_gdb, 'huc{}_final_watersheds'.format(huc8_code))
    arcpy.JoinField_management("final_watersheds", 'grid_code', seedpoly, 'POUR_ID', ['Permanent_Identifier'])

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
    arcpy.Update_analysis("final_watersheds", 'lakes_nofields', 'update_fc')
    arcpy.AddField_management('update_fc', 'dissolve_id', 'TEXT', 255)
    arcpy.MakeFeatureLayer_management('update_fc', 'update_lyr')
    arcpy.SelectLayerByAttribute_management('update_lyr', 'NEW_SELECTION', """"Permanent_Identifier" is not null""")
    arcpy.CalculateField_management('update_lyr', 'dissolve_id', '!Permanent_Identifier!', 'PYTHON')
    arcpy.SelectLayerByAttribute_management('update_lyr', 'SWITCH_SELECTION')
    arcpy.CalculateField_management('update_lyr', 'dissolve_id', '!OBJECTID!', 'PYTHON')
    arcpy.SelectLayerByAttribute_management('update_lyr', 'CLEAR_SELECTION')
    arcpy.Dissolve_management('update_lyr', "final_watersheds_bumped", 'dissolve_id', 'Permanent_Identifier FIRST')
    arcpy.DeleteField_management('final_watersheds_bumped', 'dissolve_id')

    # Select only the watersheds associated with this HU8
    wbd_hu8 = os.path.join(nhd_gdb, "WBD_HU8")
    field_name = (arcpy.ListFields(wbd_hu8, "HU*8"))[0].name
    whereClause8 =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc8_code)
    arcpy.Select_analysis(wbd_hu8, "hu8", whereClause8)

    arcpy.MakeFeatureLayer_management("final_watersheds_bumped", "final_watersheds_lyr")
    arcpy.SelectLayerByLocation_management("final_watersheds_lyr", "HAVE_THEIR_CENTER_IN", "hu8")

    arcpy.CopyFeatures_management("final_watersheds_lyr", final_watersheds_out)

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
    flowdir = r'E:\ESRI_FlowDirs\NHD_0411\D8FDR04110001p.tif'
    pour_dir = r'C:\GISData\Scratch\NHD0411\NHD0411\pourpoints0411'
    nhd_gdb = r'C:\GISData\Scratch\NHD0411\NHD0411\NHDH0411.gdb'
    out_gdb = r'C:\GISData\Scratch\Scratch.gdb'
    create_csi_watersheds(flowdir, pour_dir, nhd_gdb, out_gdb)

if __name__ == '__main__':
    main()









