# Filename = DropAndCalc.py
# Purpose: Drops unrequired fields except NHD_ID and then adds and updates geometry fields

import arcpy, os, time
fc = arcpy.GetParameterAsText(0)

def dropfields(fc):
    try:
        fields = arcpy.ListFields(fc)
        dropfields = []
        for field in fields:
            if not field.required:
                dropfields.append(field.name)
            if field.name in "NHD_ID":
                dropfields.remove(field.name)
        print "Dropping fields %s " % (dropfields)
        arcpy.DeleteField_management(fc, dropfields)
        print "Updating Geometry fields"
        arcpy.AddField_management(fc, "Area_ha","DOUBLE")
        arcpy.CalculateField_management(fc, "Area_ha", "!shape.area@hectares!", "PYTHON")
        arcpy.AddField_management(fc, "Perim_km", "DOUBLE")
        arcpy.CalculateField_management(fc, "Perim_km", "!shape.length@kilometers!", "PYTHON")
        del fields
        del dropfields
    except:
        arcpy.AddMessage("Something went wrong. Maybe you already ran this one?")
        pass
dropfields(fc)
arcpy.RefreshCatalog(fc) 
time.sleep(5)