# preprocessNWI.py
# Makes a feature class of wetlands that conform to the CSI definition of
# of wetlands and can merge seamlessly without duplicates near state borders

import arcpy, os
import csiutils as cu

def InsideState(state, nwi, lakes, outfc):
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    # Select only wetlands with their center inside this state
    # This way all wetlands will only be represented once when we merge all states

    arcpy.env.workspace = 'in_memory'
    arcpy.MakeFeatureLayer_management(nwi, "nwi_lyr")
    cu.multi_msg('Selecting wetlands with their center in the state.')
    arcpy.SelectLayerByLocation_management("nwi_lyr", 'HAVE_THEIR_CENTER_IN', state,'','NEW_SELECTION')

    # Two things to make wetlands conform to the CSI definition
    # Select only palustrine systems that aren't freshwater ponds
    # and make it impossible for wetlands to be inside lakes
    wetland_type_field = arcpy.ListFields("nwi_lyr", "WETLAND_TY*")[0].name
    filter = """"ATTRIBUTE" LIKE 'P%' AND {} <> 'Freshwater Pond'""".format(wetland_type_field)
    cu.multi_msg("Selecting only palustrine wetlands...")
    arcpy.SelectLayerByAttribute_management("nwi_lyr", "SUBSET_SELECTION", filter)
    cu.multi_msg('Erasing lakes from wetlands layer.')
    arcpy.Erase_analysis("nwi_lyr", lakes, outfc)

    # Add two fields we will use, an ID field and the area in hectares
    arcpy.AddField_management(outfc, "WET_ID", "LONG")
    arcpy.CalculateField_management(outfc, "WET_ID", "!OBJECTID!", "PYTHON")

    arcpy.AddField_management(outfc, "AreaHa", "DOUBLE")
    arcpy.CalculateField_management(outfc, "AreaHa", "!shape.area@hectares!", "PYTHON")


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



