import os
import arcpy
import NHDNetwork


def classify(nhd_gdb, output_table):
    """
    This is a wrapper tool for classifying the freshwater network connectivity of a lake. It saves the results of
    NHDNetwork.classify_waterbody_connectivity to a FileGDB table or other ArcGIS table. Additionally, after calculating
    both the maximum and permanent-only connectivity for the lake, it assigns 'Y' or "N' to
    the lake_connectivity_fluctuates flag.
    :param nhd_gdb: The file path for a high-resolution NHD or NHDPlus geodatabase for a single subregion/HU4.
    :param output_table: The path to save the output table to (suggested: FileGDB table)
    :return: The output table path
    """
    nhd_network = NHDNetwork.NHDNetwork(nhd_gdb)
    nhd_network.define_lakes(strict_minsize=False, force_lagos=True)
    waterbody_ids = nhd_network.lakes_areas.keys()
    nhd_network.define_lakes(strict_minsize=False, force_lagos=False)

    arcpy.AddMessage("Calculating all connectivity...")
    # all connectivity
    conn_class = {id:nhd_network.classify_waterbody_connectivity(id) for id in waterbody_ids}

    # permanent only
    arcpy.AddMessage("Calculating permanent connectivity...")
    nhd_network.drop_intermittent_flow()
    conn_permanent = {id:nhd_network.classify_waterbody_connectivity(id) for id in waterbody_ids}

    # make an output table
    arcpy.AddMessage("Saving output...")
    output = arcpy.CreateTable_management(os.path.dirname(output_table), os.path.basename(output_table))
    arcpy.AddField_management(output, 'lake_connectivity_class', 'TEXT', field_length=10)
    arcpy.AddField_management(output, 'lake_connectivity_permanent', 'TEXT', field_length=10)
    arcpy.AddField_management(output, 'lake_connectivity_fluctuates', 'TEXT', field_length=2)
    insert_fields = ['lake_connectivity_class',
                     'lake_connectivity_permanent',
                     'lake_connectivity_fluctuates']

    arcpy.AddMessage("Writing output...")

    # get all the ids
    arcpy.AddField_management(output, 'Permanent_Identifier', 'TEXT', field_length=40)
    write_id_names = ['Permanent_Identifier']
    if arcpy.ListFields(nhd_network.waterbody, 'lagoslakeid'):
        write_id_names.append('lagoslakeid')
        arcpy.AddField_management(output, 'lagoslakeid', 'LONG')
    if arcpy.ListFields(nhd_network.waterbody, 'nhd_merge_id'):
        write_id_names.append('nhd_merge_id')
        arcpy.AddField_management(output, 'nhd_merge_id', 'TEXT', field_length=100)

    write_id_map = {r[0]: list(r)
               for r in arcpy.da.SearchCursor(nhd_network.waterbody, write_id_names)}

    # write the table
    cursor_fields = write_id_names + insert_fields
    rows = arcpy.da.InsertCursor(output, cursor_fields)

    for id in waterbody_ids:
        write_ids = write_id_map[id]
        if conn_class[id] == conn_permanent[id]:
            fluctuates = 'N'
        else:
            fluctuates = 'Y'

        row = write_ids + [conn_class[id], conn_permanent[id], fluctuates]
        rows.insertRow(row)
    return output

def main():
    nhd_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)

    classify(nhd_gdb, output_table)

if __name__ == '__main__':
    main()
