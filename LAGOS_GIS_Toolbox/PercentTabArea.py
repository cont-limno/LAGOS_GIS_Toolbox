# Filename: PercentTabArea.py
# Purpose: Tabulate Area and get percentages for those tabulations. Then it calculates a sum of percents.

import os, arcpy
from arcpy.sa import *

zones = arcpy.GetParameterAsText(0) # Dataset that defines the zones
zonefield = arcpy.GetParameterAsText(1) # Field that holds the values that define each zone
classdata = arcpy.GetParameterAsText(2) # Dataset that defines classes to be summarized for each zone
classfield = arcpy.GetParameter(3) # The field that holds the class values
table = arcpy.GetParameterAsText(4) # The output table

# Add a field for hectares
try:
    arcpy.AddField_management(zones, "ZoneHa", "DOUBLE")
    arcpy.CalculateField_management(zones, "ZoneHa", '!shape.area@hectares!', "PYTHON")
except:
    pass

# Tabulate areas
arcpy.sa.TabulateArea(zones,zonefield,classdata,classfield,table)

# Join the "ZoneHa" Field to the output table.
arcpy.JoinField_management(table, zonefield, zones, zonefield, "ZoneHa")

# Make a list of the value fields in output table.
valuefields = []
tablefields = arcpy.ListFields(table, "VALUE_*", "DOUBLE")
pctfields = []
hafields = []
for tablefield in tablefields:
    valuefields.append(tablefield.name)

# Create a percent field and hectare field for each value and list the percent fields.
for valuefield in valuefields:
    fieldname = str(valuefield)
    pctfieldname = "PCT_" + fieldname[6:]
    hafieldname = "HA_" + fieldname[6:]
    haexp = "!%s! / 10000" % (valuefield)
    arcpy.AddField_management(table, pctfieldname, "DOUBLE")
    arcpy.AddField_management(table, hafieldname, "DOUBLE")
    exp = "!%s! / (!ZoneHa! * 10000) * 100" % (valuefield)
    arcpy.CalculateField_management(table, pctfieldname, exp, "PYTHON")
    arcpy.CalculateField_management(table, hafieldname, haexp, "PYTHON")
    pctfields.append(pctfieldname)
    hafields.append(hafieldname)

# Add a field for the sum of percentages.
arcpy.AddField_management(table, "Percent_Sum", "DOUBLE")
arcpy.AddField_management(table, "Hectare_Sum", "DOUBLE")

# Run an update cursor that adds up the percent fields for the "Percent_Sum" field value.
rows = arcpy.UpdateCursor(table)
for row in rows:
    PCT_SUM = 0
    for f in pctfields:
        PCT_SUM += row.getValue(f)
    row.Percent_Sum = PCT_SUM
    rows.updateRow(row)
    del PCT_SUM
del rows

# Run an update cursor that adds up the hectare fields for the "Hectare_Sum" field value.
rows = arcpy.UpdateCursor(table)
for row in rows:
    HA_SUM = 0
    for f in hafields:
        HA_SUM += row.getValue(f)
    row.Hectare_Sum = HA_SUM
    rows.updateRow(row)
    del HA_SUM
del rows    

# Add and calculate "Hectare_Diff" field that shows the difference in Zone and sum of Class areas in ha.
arcpy.AddField_management(table, "Hectare_Diff", "DOUBLE")
diffexp = "!ZoneHa! - !Hectare_Sum!"
arcpy.CalculateField_management(table, "Hectare_Diff", diffexp, "PYTHON")

# Delete Value fields
arcpy.DeleteField_management(table, valuefields)
    
    

