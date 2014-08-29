# preprocessNWI.py

import arcpy, os
import csiutils as cu

def InsideState(state, nwi, lakes, outfc):
    arcpy.env.workspace = 'in_memory'
    print(arcpy.Exists(nwi))
    print(arcpy.Exists(lakes))
    arcpy.MakeFeatureLayer_management(nwi, "nwi_lyr")
    cu.multi_msg('Selecting wetlands with their center in the state.')
    arcpy.SelectLayerByLocation_management("nwi_lyr", 'HAVE_THEIR_CENTER_IN', state,'','NEW_SELECTION')
    cu.multi_msg('Erasing lakes from wetlands layer.')
    arcpy.Erase_analysis("nwi_lyr", lakes, outfc)


def main():
    state = arcpy.GetParameterAsText(0) # state poly
    nwi = arcpy.GetParameterAsText(1) # nwi
    lakes = arcpy.GetParameterAsText(2)
    outfc = arcpy.GetParameterAsText(3) # output shapefile
    InsideState(state, nwi, lakes, outfc)


def test():
    state = 'C:/GISData/Single_States.gdb/Connecticut'
    nwi = r'E:\NWI_08292014\CT_wetlands.gdb\CONUS_wetlands\CONUS_wet_poly'
    lakes = r'C:\GISData\Master_Geodata\MasterGeodatabase2014_ver3.gdb\Lacustrine\LAGOS_All_Lakes_1ha'
    outfc = 'C:/GISData/Scratch/Scratch.gdb/testing_preprocess_nwi'
    InsideState(state, nwi, lakes, outfc)


if __name__ == '__main__':
    main()



