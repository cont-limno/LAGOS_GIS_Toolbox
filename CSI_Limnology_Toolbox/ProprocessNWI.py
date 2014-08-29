# preprocessNWI.py

import arcpy, os

def InsideState(state,nwi,outfc):
    mem = "in_memory"
    arcpy.env.workspace = mem
    where = """"ATTRIBUTE" LIKE 'P%' AND "WETLAND_TY" <> 'Freshwater Pond'"""
    arcpy.FeatureClassToFeatureClass_conversion(nwi, mem, "nwi", where)
    arcpy.MakeFeatureLayer_management("nwi", "nwi_lyr", where, mem)
    arcpy.SelectLayerByLocation_management("nwi_lyr", 'HAVE_THEIR_CENTER_IN', state,'','NEW_SELECTION')

    arcpy.CopyFeatures_management("nwi_lyr",outfc)

def main():
    state = arcpy.GetParameterAsText(0) # state poly
    nwi = arcpy.GetParameterAsText(1) # nwi
    outfc = arcpy.GetParameterAsText(2) # output shapefile
    InsideState(state,nwi,outfc)

if __name__ == '__main__':
    main()



