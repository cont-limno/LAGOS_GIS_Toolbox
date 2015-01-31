# Filename: Export2CSV.py
import csv, os, re
import arcpy

def TableToCSV(in_table, out_folder, new_table_name = ''):
    if new_table_name:
        name = new_table_name
    else:
        name = os.path.splitext(os.path.basename(in_table))[0]
    out_csv = os.path.join(out_folder, name + '.csv')
    fields = [f.name for f in arcpy.ListFields(in_table) if f.type <> 'Geometry' and f.name <> 'Shape_Area' and f.name <> 'Shape_Length' and f.name <> 'TARGET_FID']
    with open(out_csv, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(in_table, fields) as cursor:
            for row in cursor:
                # next line PREVENTS scientific notation in exports and change null values
                def format_value(x):
                    if x is None:
                        return 'NA'
                    elif isinstance(x, float):
                        out_value = '{0:.15f}'.format(x).rstrip('.0')
                        if not out_value:
                            out_value = '0'
                        return out_value
                    else:
                        return str(x)
                values = map(format_value, row)

##                # outputs from tools have scientific notation in them
##                # I think it's Python's fault and not ArcGIS. In Python IDE
##                # try typing 8.19 ** -5 to see what I mean, there are not
##                # "too many" digits but Python outputs scientific notation
##                # anyway.
##                def replace_scientific(x):
##                    return_value = x
##                    # if the value matches "more than 1 digit, 0 or 1 dot
##                    # symbols, 'e-', more than 1 digit" then it has been stored
##                    # in the scientific notation format, needs fixing
##                    if re.match('\d+\.?\d+[eE][-\+]\d+',x) is not None:
##                        # get the numbers we need and do the math, rounding
##                        # to 15 digits so it has no more digits than the other
##                        # double values just as a precaution for later uses
##                        mantissa, exponent = re.split('[eE]', x)
##                        # this madness keeps Python from outputting scientific
##                        # notation this time
##                        replacement = '{0:f}'.format(round(float(mantissa) ** int(exponent), 15))
##                        return_value = replacement
##                    return str(return_value)
##                # this is the step that actually applies to function to all values
##                values = map(replace_scientific, values)
                f.write(','.join(values)+'\n')

def main():
    in_table = arcpy.GetParameterAsText(0)
    out_folder = arcpy.GetParameterAsText(1)
    TableToCSV(in_table, out_folder)

if __name__ == '__main__':
    main()
