# Filename: WetlandOrder.py
# Purpose: Assigns a class to wetlands based on their connectivity to the landscape.
import arcpy
from arcpy import env
from arcpy.sa import *
import lagosGIS


def split_strahler(stream_area_fc, streams, out_area_fc):
    """This function splits up the NHDArea feature class, which does not
    start and stop polygons at confluences, by creating break points near the
    confluences to split up the polygons. Then, it adds the Strahler value from
    the stream centerline."""
    # 1) Generate euclidean allocation raster from streams (use OBJECTID)
    # 2) Convert euclidean allocation raster to polygons
    # 3) Join allocation polygons "gridcode" to streams "OBJECTID" so that
    #    Strahler value is attached to allocation polygon
    # 4) Use identity function to split up the StreamRiver polygons at the
    #    allocation polygon boundaries, and add the Strahler values
    old_workspace = env.workspace
    env.workspace = 'in_memory'
    lagosGIS.multi_msg("Splitting stream area polygons between confluences and joining 1) Strahler order to them...")
    lagosGIS.multi_msg('next messages for testing')
    arcpy.CheckOutExtension('Spatial')
    lagosGIS.multi_msg('euc')
    euc = EucAllocation(streams, cell_size = '50', source_field = 'OBJECTID')
    arcpy.CheckInExtension('Spatial')
    lagosGIS.multi_msg('conversion')
    arcpy.RasterToPolygon_conversion(euc, 'allocation_polys')
    stream_id_field = arcpy.ListFields(streams, 'Permanent_')[0].name
    lagosGIS.multi_msg('join')
    arcpy.JoinField_management('allocation_polys', 'grid_code', streams, 'OBJECTID', ['Strahler', 'LengthKm', stream_id_field])
    lagosGIS.multi_msg('identity')
    arcpy.Identity_analysis(stream_area_fc, 'allocation_polys', out_area_fc)
    env.workspace = old_workspace
    lagosGIS.multi_msg("Splitting strema area polygons finished.")

def wetland_order(rivex, stream_area_fc, nwi, out_fc):
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    arcpy.env.extent = nwi

    # Buffer the wetland perimeters by 30 meters
    lagosGIS.multi_msg('Creating 30m wetland buffers...')
    arcpy.Buffer_analysis(nwi, "wetland_buffers", "30 meters", "OUTSIDE_ONLY")
    arcpy.env.extent = "wetland_buffers"

    lagosGIS.multi_msg('Preparing for river line and area merge...')
    arcpy.CopyFeatures_management(rivex, 'rivex_extent')
    arcpy.CopyFeatures_management(stream_area_fc, 'stream_area_extent')
    arcpy.MakeFeatureLayer_management('rivex_extent', 'rivex_lyr')
    arcpy.SelectLayerByLocation_management('rivex_lyr', 'COMPLETELY_WITHIN', stream_area_fc)
    arcpy.CopyFeatures_management('rivex_lyr', 'rivex_for_splitting')
    arcpy.SelectLayerByAttribute_management('rivex_lyr', 'SWITCH_SELECTION')
    arcpy.CopyFeatures_management('rivex_lyr', 'rivex_not_areas')
    split_strahler('stream_area_extent', 'rivex_for_splitting', 'stream_area_split')

    # areas TO lines
    arcpy.PolygonToLine_management('stream_area_split', 'streamarea_to_line', False)

    # Merge features together
    arcpy.Merge_management(['streamarea_to_line', 'rivex_not_areas'], 'merged_rivers', 'NO_TEST')

    # FOR THE LINE-BASED PORTION
    # Spatial join connected wetlands and streams
    ##################Field Maps########################
    fms = arcpy.FieldMappings()
    fm_strahlermax = arcpy.FieldMap()
    fm_strahlersum = arcpy.FieldMap()
    fm_lengthkm = arcpy.FieldMap()
    fm_wetid = arcpy.FieldMap()

    fm_strahlermax.addInputField('merged_rivers', "Strahler")
    fm_strahlersum.addInputField('merged_rivers', "Strahler")
    fm_lengthkm.addInputField('merged_rivers', "LengthKm")
    fm_wetid.addInputField("wetland_buffers", "WET_ID")

    fm_lengthkm.mergeRule = 'Sum'
    fm_strahlermax.mergeRule = 'Max'
    fm_strahlersum.mergeRule = 'Sum'

    lengthkm_name = fm_lengthkm.outputField
    lengthkm_name.name = 'StreamKm'
    lengthkm_name.aliasName = 'StreamKm'
    fm_lengthkm.outputField = lengthkm_name

    strahlermax_name = fm_strahlermax.outputField
    strahlermax_name.name = 'StrOrdMax'
    strahlermax_name.aliasName = 'StrOrdMax'
    fm_strahlermax.outputField = strahlermax_name

    strahlersum_name = fm_strahlersum.outputField
    strahlersum_name.name = 'StrOrdSum'
    strahlersum_name.aliasName = 'StrOrdSum'
    fm_strahlersum.outputField = strahlersum_name

    fms.addFieldMap(fm_strahlermax)
    fms.addFieldMap(fm_strahlersum)
    fms.addFieldMap(fm_lengthkm)
    fms.addFieldMap(fm_wetid)
    #####################################################

    arcpy.SpatialJoin_analysis("wetland_buffers", 'merged_rivers', "wetland_spjoin_streams", '', '', fms)

    # Get the stream count from the join count
    lagosGIS.rename_field("wetland_spjoin_streams", 'Join_Count', "StreamCnt", True)

    # Join the new fields back to the original feature class based on WET_ID
    join_fields = ['StrOrdMax', 'StrOrdSum', 'StreamKm', 'StreamCnt']
    arcpy.CopyFeatures_management(nwi, out_fc)
    arcpy.JoinField_management(out_fc, 'WET_ID', 'wetland_spjoin_streams', 'WET_ID', join_fields)

    # Set these to 0 where there is no connection
    lagosGIS.redefine_nulls(out_fc, join_fields, [0, 0, 0, 0])

    # Classify VegType: 4 options based on class code in ATTRIBUTE field
    arcpy.AddField_management(out_fc, "VegType", "TEXT")
    with arcpy.da.UpdateCursor(out_fc, ["ATTRIBUTE", "VegType"]) as cursor:
        for row in cursor:
            attr_abbv = row[0][:3]
            if attr_abbv == "PEM" or attr_abbv == "PAB":
                row[1] = "PEMorPAB"
            elif attr_abbv == "PFO":
                row[1] = "PFO"
            elif attr_abbv == "PSS":
                row[1] = "PSS"
            else:
                row[1] = "Other"
            cursor.updateRow(row)

    # Determine the regime from the letter code. Examples: PSS1E ---> E,
    #  PEM1/SS1Fb --> F
    class_codes = 'RB UB AB US ML EM SS FO'.split()
    regime_codes = 'A B C E F G H J K'.split()
    arcpy.AddField_management(out_fc, "Regime", "TEXT")
    with arcpy.da.UpdateCursor(out_fc, ["ATTRIBUTE", "Regime"]) as cursor:
        for row in cursor:
            # All the wetlands are already palustrine, so if we remove the class
            # codes, any capital letters left besides the P in front
            # are the regime code
            # example codes: PEM1E, PSS1/EM1E, PEM1/5C, PUSA, PSSf
            # If you ever can figure out the regex for this instead, go ahead.
            code_value = row[0]
            regime_value = 'unknown'
            # this bit searches for the class codes and replaces them with nothing
            # this is necessary because meaning of A, B, E, F is context dependent
            for class_code in class_codes:
                if class_code in code_value:
                    code_value = code_value.replace(class_code, '')
            for char in code_value:
                if char in regime_codes:
                    regime_value = char
            row[1] = regime_value
            cursor.updateRow(row)

    # Calculate WetOrder from StrOrdSum
    arcpy.AddField_management(out_fc,"WetOrder", "TEXT")
    with arcpy.da.UpdateCursor(out_fc, ["StrOrdSum", "WetOrder"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                row[1] = "Isolated"
            elif row[0] == 1:
                row[1] = "Single"
            elif row[0] == None:
                row[1] = "Isolated"
            else:
                row[1] = "Connected"
            cursor.updateRow(row)
    arcpy.Delete_management('in_memory')

def test():
    # User input parameters:
    rivex = 'C:/GISData/Rivex.gdb/Rivex'
    stream_area_fc = r'C:\GISData\Scratch\Scratch.gdb\All_StreamRiver_Area_Final'
    nwi =  r'C:\GISData\Wetlands_Update_Aug2014.gdb\Rhode_Island_NWI'
    out_fc ='C:/GISData/Wetlands_Update_Sept2014_ORDER.gdb/Rhode_Island_Wetlands'
    wetland_order(rivex, stream_area_fc, nwi, out_fc)

def main():
    # User input parameters:
    rivex = arcpy.GetParameterAsText(0) # A shapefile of rivers that has the "Strahler" field produced by RivEx extension.
    stream_area_fc = arcpy.GetParameterAsText(1) # shapefile of NHDAreas merged together with duplicates deleted
    nwi = arcpy.GetParameterAsText(2) # NWI feature class
    out_fc = arcpy.GetParameterAsText(3) # OPTIONAL: save as fc
    wetland_order(rivex, stream_area_fc, nwi, out_fc)

if __name__ == '__main__':
    main()
























