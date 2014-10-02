# ConnectedWetlands.py
# Characterizes each lake according to its wetland connections
# Output table has one row PER LAKE

import os
import arcpy
from arcpy import env
import csiutils as cu
from polygons_in_zones import polygons_in_zones

def connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table):
    env.workspace = 'in_memory'
    env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    arcpy.Buffer_analysis(lakes_fc, 'lakes_30m', '30 meters')

    arcpy.FeatureToLine_management('lakes_30m', 'shorelines')

    # 3 selections for the wetlands types we want to look at
    openwater_exp = """"VegType" = 'PEMorPAB'"""
    forested_exp = """"VegType" = 'PFO'"""
    scrubshrub_exp = """"VegType" = 'PSS'"""
    other_exp = """"VegType" = 'Other'"""
    all_exp = ''


    selections = [all_exp, forested_exp, scrubshrub_exp, openwater_exp, other_exp]
    temp_tables = ['AllWetlands', 'ForestedWetlands', 'ScrubShrubWetlands', 'OpenWaterWetlands', 'OtherWetlands']

    # for each wetland type, get the count of intersection wetlands, the total area
    # of the lake that is overlapping with wetlands, and the length of the lake
    # shoreline that is within a wetland polygon
    for sel, temp_table in zip(selections, temp_tables):
        print("Creating temporary table for wetlands where {0}".format(sel))
        # this function adds the count and the area using the lake as the zone
        polygons_in_zones('lakes_30m', lake_id_field, wetlands_fc, temp_table, sel, contrib_area = True)

        # make good field names now rather than later

        # TESTING ONLY print field names
        print('FIELD NAMES')
        print([f.name for f in arcpy.ListFields(temp_table)])
        new_fields = ['Poly_Overlapping_AREA_ha', 'Poly_Overlapping_AREA_pct', 'Poly_Count', 'Poly_Contributing_AREA_ha']
        for f in new_fields:
            print f
            print(f.replace('Poly', temp_table))
            print(arcpy.Exists(temp_table))
            cu.rename_field(temp_table, f, f.replace('Poly', temp_table), True)

        # shoreline calculation
        # using the Shape_Length field so can't do this part in memory
        shoreline_gdb = cu.create_temp_GDB('shoreline')
        selected_wetlands = os.path.join(shoreline_gdb, 'wetlands')
        arcpy.Select_analysis(wetlands_fc, selected_wetlands, sel)
        intersect_output = os.path.join(shoreline_gdb, "intersect")
        arcpy.Intersect_analysis(['shorelines', selected_wetlands], intersect_output)
        arcpy.Statistics_analysis(intersect_output, 'intersect_stats', [['Shape_Length', 'SUM']], lake_id_field)
        cu.one_in_one_out('intersect_stats', ['SUM_Shape_Length'], lakes_fc, lake_id_field, 'temp_shoreline_table')
        cu.redefine_nulls('temp_shoreline_table', ['SUM_Shape_Length'], [0])
        shoreline_field = temp_table + "_Shoreline_Km"
        arcpy.AddField_management('temp_shoreline_table', shoreline_field, 'DOUBLE')
        arcpy.CalculateField_management('temp_shoreline_table', shoreline_field, '!SUM_Shape_Length!/1000', 'PYTHON')

        # join the shoreline value to the temp_table
        arcpy.JoinField_management(temp_table, lake_id_field, 'temp_shoreline_table', lake_id_field, shoreline_field)

        # clean up shoreline intermediates
        for item in [shoreline_gdb, 'intersect_stats', 'temp_shoreline_table']:
            arcpy.Delete_management(item)

    # join em up and copy to final
    temp_tables.remove('AllWetlands')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('AllWetlands', lake_id_field, t, lake_id_field)
        # sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('AllWetlands', ef, 'Double')
                arcpy.CalculateField_management('AllWetlands', ef, '0', 'PYTHON')
            continue
    # remove all the extra zone fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('AllWetlands', 'Permanent_Identifier_*')]
    for f in drop_fields:
        arcpy.DeleteField_management('AllWetlands', f)

    # remove all the overlapping metrics, which do not apply by definition
    fields = [f.name for f in arcpy.ListFields('AlLWetlands')]
    for f in fields:
        if 'Overlapping' in f:
            arcpy.DeleteField_management('AllWetlands', f)
    arcpy.CopyRows_management('AllWetlands', out_table)

    for item in ['AllWetlands'] + temp_tables:
        try:
            arcpy.Delete_management(item)
        except:
            continue

def main():
    lakes_fc = arcpy.GetParameterAsText(0)
    lake_id_field = arcpy.GetParameterAsText(1)
    wetlands_fc = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table)

def test():
    lakes_fc = r'C:\GISData\Master_Geodata\MasterGeodatabase2014_ver4.gdb\Lacustrine\LAGOS_All_Lakes_4ha'
    lake_id_field = 'Permanent_Identifier'
    wetlands_fc = r'C:\GISData\Master_Geodata\MasterGeodatabase2014_ver4.gdb\Palustrine\Wetlands'
    out_table = r'C:\GISData\Attribution_Sept2014.gdb/LakeWetlandConnections_FIXED'
    connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table)

##    lakes_fc = r'C:\GISData\Scratch\Scratch.gdb\Lakes_OCT1'
##    lake_id_field = 'Permanent_Identifier'
##    wetlands_fc = r'C:\GISData\Scratch\Scratch.gdb\Wetlands_OCT1'
##    out_table = r'C:\GISData\Scratch\Scratch.gdb\ConnectedWetlands_OCT1TEST'
##    connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table)

if __name__ == '__main__':
    main()





##def connected_wetlands(nhd, nwi, out_table):
##    # name NHD feature classes with variables
##    flowline = os.path.join(nhd, "Hydrography", "NHDFlowline")
##    waterbody = os.path.join(nhd, "Hydrography", "NHDWaterbody")
##    network = os.path.join(nhd, "Hydrography", "HYDRO_NET")
##    junction = os.path.join(nhd, "Hydrography", "HYDRO_NET_Junctions")
##
##    # Set up environments
##    env.outputCoordinateSystem = arcpy.SpatialReference(102039)
##    env.extent = flowline
##
##    # make filtered layers of lakes and wetlands
##    # lakes_selection eliminates most non-perennial, non-lacustrine features by FCode
##    # 1 hectare lakes included
##    lakes_selection = '''"AreaSqKm" >=0.01 AND ( "FType" = 390 OR "FType" = 436) AND\
##         ("FCode" = 39000 OR "FCode" = 39004 OR "FCode" = 39009 OR "FCode" = 39010 OR\
##          "FCode" = 39011 OR "FCode" = 39012 OR "FCode" = 43600 OR "FCode" = 43613 OR\
##          "FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR\
##          "FCode" = 43619 OR "FCode" = 43621) OR ("Fcode" = 43601 AND "AreaSqKm" >= 0.1)'''
##    arcpy.MakeFeatureLayer_management(waterbody, 'oneha_lakes')
##
####    arcpy.MakeFeatureLayer_management(nwi, 'nwi_lyr')
####    arcpy.AddField_management('nwi_lyr', 'AreaHa', 'DOUBLE')
####    arcpy.CalculateField_management('nwi_lyr', 'AreaHa', '!shape.area@hectares!', 'PYTHON')
##
##    # Filter expressions for NWI wetland types
##    forested_exp = """ "WETLAND_TY" = 'Freshwater Forested/Shrub Wetland' """
##    emergent_exp = """ "WETLAND_TY" = 'Freshwater Emergent Wetland' """
##    other_exp = """ "WETLAND_TY" = 'Other' """
##
##    expressions = [forested_exp, emergent_exp, other_exp]
##    for expression in expressions:
##        arcpy.MakeFeatureLayer_management(nwi, 'wetlands', forested_exp)
##        arcpy.SpatialJoin_analysis('oneha_lakes', 'wetlands'
##
##
### Spatial Join lakes to each wetland type
##for wl in wl_list:
##    fieldmappings = arcpy.FieldMappings()
##    fieldmap_id = arcpy.FieldMap()
##    fieldmap_ty = arcpy.FieldMap()
##    fieldmap_wetha = arcpy.FieldMap()
##    fieldmap_id.addInputField(oneha, "Permanent_")
##    fieldmap_ty.addInputField(wl, "WETLAND_TY")
##    fieldmap_wetha.addInputField(wl, "WETLAND_HA")
##    fieldmap_wetha.mergeRule = 'SUM'
##    fieldmappings.addFieldMap(fieldmap_id)
##    fieldmappings.addFieldMap(fieldmap_ty)
##    fieldmappings.addFieldMap(fieldmap_wetha)
##    arcpy.SpatialJoin_analysis(oneha, wl, os.path.join(scratch, wl[3:]), '', '', fieldmappings)
##    outwl = os.path.join(scratch, wl[3:])
##    name = os.path.basename(outwl)
##    arcpy.AddField_management(outwl, name + "HA", "DOUBLE")
##    arcpy.CalculateField_management(outwl, name + "HA", "!WETLAND_HA!", "PYTHON")
##    field = name + "HA"
##    arcpy.AddField_management(outwl, name + "CNT", "LONG")
##    field2 = name + "CNT"
##    arcpy.CalculateField_management(outwl, name + "CNT", "!Join_Count!", "PYTHON")
##    arcpy.JoinField_management(table, "Permanent_", outwl, "Permanent_", field )
##    arcpy.JoinField_management(table, "Permanent_", outwl, "Permanent_", field2 )
##    del fieldmappings
##
##
##arcpy.TableToTable_conversion(table, outfolder, "ConnectedWetlands.txt")
##
##
##
### User defined input parameters
##nhd = arcpy.GetParameterAsText(0) # NHD 24k state geodatabase
##nwi = arcpy.GetParameterAsText(1) # National wetlands inventory "CONUS_wet_poly" feature class for a state
###ws = arcpy.GetParameterAsText(2) # Watersheds - usually the output from cumulative watersheds tool.
##outfolder = arcpy.GetParameterAsText(2)
##
##
##

### Environmental settings
##albers = arcpy.SpatialReference()
##albers.factoryCode = 102039
##albers.create()
##arcpy.env.outputCoordinateSystem = albers
##arcpy.env.overwriteOutput = "TRUE"
##mem = "in_memory"
##arcpy.env.parallelProcessingFactor = "100%"
##
### Make an output gdb
##arcpy.CreateFileGDB_management(outfolder, "scratch")
##scratch = os.path.join(outfolder, "scratch.gdb")
##arcpy.RefreshCatalog(outfolder)
##
### Filter expression for NHDWaterbody that eliminate most non-perrenial, non-lacustrine features by Fcode at a 1 & 10 ha min size.
##filter = '''"AreaSqKm" >=0.01 AND ( "FType" = 390 OR "FType" = 436) AND\
##         ("FCode" = 39000 OR "FCode" = 39004 OR "FCode" = 39009 OR "FCode" = 39010 OR\
##          "FCode" = 39011 OR "FCode" = 39012 OR "FCode" = 43600 OR "FCode" = 43613 OR\
##          "FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR\
##          "FCode" = 43619 OR "FCode" = 43621) OR ("Fcode" = 43601 AND "AreaSqKm" >= 0.1)'''
##
##
### NHD feature class variables:
##flowline = os.path.join(nhd, "Hydrography", "NHDFlowline")
##waterbody = os.path.join(nhd, "Hydrography", "NHDWaterbody")
##network = os.path.join(nhd, "Hydrography", "HYDRO_NET")
##junction = os.path.join(nhd, "Hydrography", "HYDRO_NET_Junctions")




### Make layer of NWI
##arcpy.env.workspace = mem
##arcpy.MakeFeatureLayer_management(nwi, os.path.join(mem, "nwi_lyr"))
##nwi_lyr = os.path.join(mem, "nwi_lyr")
##
### Make a layer of filtered one hectare lakes
##arcpy.MakeFeatureLayer_management(waterbody, os.path.join(mem, "oneha_lyr"), filter)
##oneha_lyr = os.path.join(mem, "oneha_lyr")
##
### Select wetlands intersecting lakes
##arcpy.SelectLayerByLocation_management(nwi_lyr, "INTERSECT", oneha_lyr, "", "NEW_SELECTION")
##arcpy.CopyFeatures_management(nwi_lyr, os.path.join(mem, "wet"))
##wet = os.path.join(mem, "wet")
##
### Add a hectares field to wetlands
##arcpy.AddField_management(wet, "WETLAND_HA", "DOUBLE")
##arcpy.CalculateField_management(wet, "WETLAND_HA", "!shape.area@hectares!", "PYTHON")
##
### Filter expressions for NWI wetland types
##forested_exp = """ "WETLAND_TY" = 'Freshwater Forested/Shrub Wetland' """
##emergent_exp = """ "WETLAND_TY" = 'Freshwater Emergent Wetland' """
##other_exp = """ "WETLAND_TY" = 'Other' """
##
### Make 3 wetland feature classes
##arcpy.MakeFeatureLayer_management(wet, os.path.join(outfolder, "wet.lyr"))
##wet_lyr = os.path.join(outfolder, "wet.lyr")
##
##arcpy.SelectLayerByAttribute_management(wet_lyr, "NEW_SELECTION", forested_exp)
##arcpy.CopyFeatures_management(wet_lyr, os.path.join(scratch, "wl_Forest"))
##forested = os.path.join(scratch, "wl_Forest")
##
##arcpy.SelectLayerByAttribute_management(wet_lyr, "NEW_SELECTION", emergent_exp)
##arcpy.CopyFeatures_management(wet_lyr, os.path.join(scratch, "wl_Emerge"))
##emergent = os.path.join(scratch, "wl_Emerge")
##
##arcpy.SelectLayerByAttribute_management(wet_lyr, "NEW_SELECTION", other_exp)
##arcpy.CopyFeatures_management(wet_lyr, os.path.join(scratch, "wl_Other"))
##other = os.path.join(scratch, "wl_Other")




### Make a list of wetland feature classes
##arcpy.env.workspace = scratch
##wl_list = arcpy.ListFeatureClasses("wl_*")
##
### Write 1ha waterbodies to scratch.
##arcpy.CopyFeatures_management(oneha_lyr, os.path.join(outfolder, "oneha.shp"))
##oneha = os.path.join(outfolder, "oneha.shp")
##try:
##    arcpy.DeleteField_management(oneha,'FCODE')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'FDate')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'Resolution')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha,'GNIS_ID')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'GNIS_NAME')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'AreaSqKm')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'Elevation')
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'FType' )
##except:
##    pass
##try:
##    arcpy.DeleteField_management(oneha, 'ReachCode' )
##except:
##    pass
##
##
##table = oneha
##
##
##
