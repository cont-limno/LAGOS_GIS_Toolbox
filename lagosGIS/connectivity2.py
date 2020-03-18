import os
import arcpy
import nhdplushr_tools as hr

def classify_all_lake_conn(nhd_gdb, output_table):
    nhd_network = hr.NHDNetwork(nhd_gdb)
    nhd_network.define_lakes(strict_minsize=False) # calc conn for a few extra lakes to match LAGOS pop
    waterbody_ids = nhd_network.lakes_areas.keys()

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

    # if the nhd database has nhd_merge_id (LAGOS de-duplication id) in it, report that, otherwise use permanent_identifier
    if arcpy.ListFields(nhd_network.waterbody, '*nhd_merge_id*'):
        id_name = 'nhd_merge_id'
        arcpy.AddField_management(output, 'nhd_merge_id', 'TEXT', field_length=100)
        lagosid = {r[0]:r[1]
                   for r in arcpy.da.SearchCursor(nhd_network.waterbody, ['Permanent_Identifier', 'nhd_merge_id'])}
    else:
        id_name = 'Permanent_Identifier'
        arcpy.AddField_management(output, 'Permanent_Identifier', field_length=40)

    insert_fields.append(id_name)
    rows = arcpy.da.InsertCursor(output, insert_fields)

    # write the table
    for id in waterbody_ids:
        if conn_class[id] == conn_permanent[id]:
            fluctuates = 'N'
        else:
            fluctuates = 'Y'

        if id_name == 'nhd_merge_id':
            write_id = lagosid[id]
        else:
            write_id = id

        row = (conn_class[id], conn_permanent[id], fluctuates, write_id)
        rows.insertRow(row)

def main():
    nhd_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)

    classify_all_lake_conn(nhd_gdb, output_table)

if __name__ == '__main__':
    main()
