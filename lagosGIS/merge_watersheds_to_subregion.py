import os, re
import arcpy
import csiutils as cu

def merge_watersheds(watershed_fcs_list, nhd_gdb, out_fc):
    """Merges watershed fcs that are at HU8 level to subregion level. Checks
    whether there are as many feature classes being merged as there are HU8s
    in the subregion and issues an error, warning, or okay message accordingly."""
    arcpy.env.workspace = 'in_memory'
    # get this hu4 boundary
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()
    wbd_hu4 = os.path.join(nhd_gdb, "WBD_HU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    hu8 = os.path.join(nhd_gdb, 'WBD_HU8')
    field_name_8 = (arcpy.ListFields(hu8, "HU*8"))[0].name
    arcpy.MakeFeatureLayer_management(hu8, 'HU8_lyr')
    whereClause = """"{0}" LIKE '{1}%'""".format(field_name_8, huc4_code)
    arcpy.SelectLayerByAttribute_management('HU8_lyr', 'NEW_SELECTION', whereClause)
    arcpy.CopyFeatures_management('HU8_lyr', 'HU8_selected')
    hu8s_selected = [row[0] for row in arcpy.da.SearchCursor('HU8_selected', field_name_8)]

    if len(hu8s_selected) < len(watershed_fcs_list):
        arcpy.AddError("Number of feature classes in input list exceeds number of HU8s in subregion. Check list and try again.")
    elif len(hu8s_selected) > len(watershed_fcs_list):
        arcpy.AddWarning("Number of features classes in input list is fewer than number of HU8s in subregion. Tool will proceed. Check that result matches your expectations.")
    elif len(hu8s_selected) == len(watershed_fcs_list):
        arcpy.AddMessage("There are as many inputs as there are HU8s in the subregion.")

    # This typically works out faster than merging when there are LOTS of features
    first_fc = watershed_fcs_list.pop(0)
    arcpy.CopyFeatures_management(first_fc, out_fc)
    cu.lengthen_field(out_fc, 'Permanent_Identifier', 255)
    for fc in watershed_fcs_list:
        arcpy.Append_management(watershed_fcs_list, out_fc, 'NO_TEST')

def main():
    watershed_fcs_list = arcpy.GetParameterAsText(0).split(';')
    nhd_gdb = arcpy.GetParameterAsText(1)
    out_fc = arcpy.GetParameterAsText(2)
    merge_watersheds(watershed_fcs_list, nhd_gdb, out_fc)

def test():
    arcpy.env.workspace = 'C:/GISData/Scratch/new_watersheds_nov27gdb'
    fcs = arcpy.ListFeatureClasses('huc0411*')
    watershed_fcs_list = fcs
    nhd_gdb = 'E:/nhd/fgdb/NHDH0411.gdb'
    out_fc = 'C:/GISData/Scratch/Scratch.gdb/test_watersheds_merge'
    merge_watersheds(fcs, nhd_gdb, out_fc)

if __name__ == '__main__':
    main()

