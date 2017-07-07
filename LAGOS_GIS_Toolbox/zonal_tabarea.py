import datetime
import os
import tempfile
import xml.etree.ElementTree as ET
import arcpy
from arcpy import env
import csiutils as cu


# this method is ludicrous but works for today. 2017-06-02 njs
def edit_metadata(out_table, zone_fc, in_value_raster,
                  translator = 'C:\Program Files (x86)\ArcGIS\Desktop10.3\Metadata\Translator\ArcGIS2FGDC.xml'):
    #translator path is not robust to changes in ArcGIS version or installation location right now
    f = os.path.join(tempfile.gettempdir(), 'temp_metadata.xml')
    arcpy.ExportMetadata_conversion(out_table, translator, f)

    tree = ET.parse(f)
    root = tree.getroot()

    template_string = '''<dataqual>
        <logic></logic>
        <complete></complete>
        <lineage>
          <srcinfo>
            <srccite>
              <citeinfo>
                <origin></origin>
                <pubdate></pubdate>
                <title></title>
                <geoform></geoform>
                <pubinfo>
                  <pubplace></pubplace>
                  <publish></publish>
                </pubinfo>
                <onlink></onlink>
              </citeinfo>
            </srccite>
            <srcscale></srcscale>
            <typesrc></typesrc>
            <srctime>
              <timeinfo>
                <sngdate>
                  <caldate></caldate>
                </sngdate>
              </timeinfo>
              <srccurr></srccurr>
            </srctime>
            <srccitea></srccitea>
            <srccontr></srccontr>
          </srcinfo>
          <procstep>
            <procdesc>
    </procdesc>
            <procdate></procdate>
          </procstep>
        </lineage>
      </dataqual>'''

    new_src_template_string = '''
    <srcinfo>
            <srccite>
              <citeinfo>
                <origin></origin>
                <pubdate></pubdate>
                <title></title>
                <geoform></geoform>
                <pubinfo>
                  <pubplace></pubplace>
                  <publish></publish>
                </pubinfo>
                <onlink></onlink>
              </citeinfo>
            </srccite>
            <srcscale></srcscale>
            <typesrc></typesrc>
            <srctime>
              <timeinfo>
                <sngdate>
                  <caldate></caldate>
                </sngdate>
              </timeinfo>
              <srccurr></srccurr>
            </srctime>
            <srccitea></srccitea>
            <srccontr></srccontr>
          </srcinfo>'''

    dq_template = ET.fromstring(template_string)

    dataqual = root.find('dataqual')
    if dataqual is None:
        root.insert(1, dq_template)
    dataqual = root.find('dataqual')

    github_tool_location = 'https://github.com/cont-limno/LAGOS_GIS_Toolbox/blob/master/LAGOS_GIS_Toolbox/zonal_tabarea.py'
    dataqual.find('.//procdesc').text = github_tool_location
    dataqual.find('.//procdate').text = str(datetime.date.today())
    dataqual.find('.//proctime').text = str(datetime.datetime.now())

    dataqual.find('.//srccontr').text = "Zones summarized"
    dataqual.find('.//title').text = zone_fc

    new_src_template = ET.fromstring(new_src_template_string)
    lineage = root.find('.//lineage')
    insert_pos = len([child for child in lineage if child.tag == 'srcinfo'])
    lineage.insert(insert_pos, new_src_template)
    new_src = lineage.findall('.//srcinfo')[insert_pos]

    new_src.find('.//srccontr').text = "Raster values summarized to zones"
    new_src.find('.//title').text = in_value_raster

    tree.write(f)
    arcpy.ImportMetadata_conversion(f, "FROM_FGDC", out_table)

    os.remove(f)

def refine_zonal_output(t, is_thematic):
    """Makes a nicer output for this tool. Rename some fields, drop unwanted
        ones, calculate percentages using raster AREA before deleting that
        field."""

    drop_fields = ['COUNT', 'AREA', 'RANGE', 'SUM', 'ZONE_CODE']
    if is_thematic:
        fields = arcpy.ListFields(t, "VALUE*")
        for f  in fields:
            # convert area to hectares in a new field
            ha_field = f.name.replace("VALUE", "Ha")
            arcpy.AddField_management(t, ha_field, f.type)
            expr = "!%s!/10000" % f.name
            arcpy.CalculateField_management(t, ha_field, expr, "PYTHON")

            # find percent of total area in a new field
            pct_field = f.name.replace("VALUE", "Pct")
            arcpy.AddField_management(t, pct_field, f.type)
            expr = "100 * !%s!/!AREA!" % f.name
            arcpy.CalculateField_management(t, pct_field, expr, "PYTHON")

            #Delete the old field
            arcpy.DeleteField_management(t, f.name)

    else:
        # continuous variables don't have these in the output
        drop_fields = drop_fields + ['VARIETY', 'MAJORITY', 'MINORITY', 'MEDIAN']

    for df in drop_fields:
        try:
            arcpy.DeleteField_management(t, df)
        except:
            continue

def stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic):
    arcpy.CheckOutExtension("Spatial")
    arcpy.AddMessage("Calculating zonal statistics...")
    temp_zonal_table = 'in_memory/zonal_stats_temp'
    temp_entire_table = 'in_memory/temp_entire_table'

    # calculate/doit
    env.snapRaster = in_value_raster
    env.cellSize = in_value_raster

    # this has to be on disk for some reason to avoid background processing
    # errors thrown up at random
    # hence we get the following awkward horribleness
    use_convert_raster = False

    try:
        arcpy.sa.ZonalStatisticsAsTable(zone_fc, zone_field, in_value_raster,
                                temp_zonal_table, 'DATA', 'ALL')
    # with Permanent_Identifier as the zone_field, background processing errors
    # and another error get thrown up at random
    # it's faster to do zonal stats as above but if it fails (which it does
    # pretty quickly, usually), do this way which always works but takes
    # twice as long on large rasters
    except:
        temp_workspace = cu.create_temp_GDB('temp_zonal')
        convert_raster = os.path.join(temp_workspace,
                       cu.shortname(zone_fc) + '_converted')
        use_convert_raster = True

        arcpy.AddMessage('Creating raster {0}'.format(convert_raster))
        arcpy.PolygonToRaster_conversion(zone_fc, zone_field, convert_raster)
        arcpy.sa.ZonalStatisticsAsTable(convert_raster, zone_field, in_value_raster,
                                    temp_zonal_table, "DATA", "ALL")

    if is_thematic:
        #for some reason env.celLSize doesn't work
        desc = arcpy.Describe(in_value_raster)
        cell_size = desc.meanCelLHeight

        # calculate/doit
        temp_area_table = 'in_memory/tab_area_temp'
        arcpy.AddMessage("Tabulating areas...")

        if use_convert_raster:
            arcpy.sa.TabulateArea(convert_raster, zone_field, in_value_raster,
                                'Value', temp_area_table, cell_size)
        else:
            arcpy.sa.TabulateArea(zone_fc, zone_field, in_value_raster,
                                'Value', temp_area_table, cell_size)

        # making the output table
        arcpy.CopyRows_management(temp_area_table, temp_entire_table)
        zonal_stats_fields = ['AREA']
        arcpy.JoinField_management(temp_entire_table, zone_field, temp_zonal_table, zone_field, zonal_stats_fields)

        # cleanup
        arcpy.Delete_management(temp_area_table)

    if not is_thematic:
        # making the output table
        arcpy.CopyRows_management(temp_zonal_table, temp_entire_table)

    arcpy.AddMessage("Refining output table...")
    refine_zonal_output(temp_entire_table, is_thematic)



    #final table gets a record even for no-data zones
    keep_fields = [f.name for f in arcpy.ListFields(temp_entire_table)]
    if zone_field.upper() in keep_fields:
        keep_fields.remove(zone_field.upper())
    if zone_field in keep_fields:
        keep_fields.remove(zone_field)
    cu.one_in_one_out(temp_entire_table, keep_fields, zone_fc, zone_field, out_table)
##    cu.redefine_nulls(out_table, keep_fields, ["NA"]* len(keep_fields))

    # count whether all zones got an output record or not)
    out_count = int(arcpy.GetCount_management(temp_entire_table).getOutput(0))
    in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
    count_diff = in_count - out_count
    if count_diff > 0:
        warn_msg = ("WARNING: {0} features are missing in the output table"
                    " because they are too small for this raster's"
                    " resolution. This may be okay depending on your"
                    " application.").format(count_diff)
        arcpy.AddWarning(warn_msg)
        print(warn_msg)

    arcpy.AddMessage("Saving details to output metadata...")
    edit_metadata(out_table, zone_fc, in_value_raster)

    # cleanup
    arcpy.Delete_management(temp_zonal_table)
    arcpy.Delete_management(temp_entire_table)
    if use_convert_raster:
        arcpy.Delete_management(os.path.dirname(temp_workspace))
    arcpy.CheckInExtension("Spatial")

    return [out_table, count_diff]

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(4)
    is_thematic = arcpy.GetParameter(3) #boolean
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)


def test():
    test_gdb = r'C:\Users\smithn78\PycharmProjects\LAGOS_GIS_Toolbox\TestData_0411.gdb'
    zone_fc = r'C:\Users\smithn78\PycharmProjects\LAGOS_GIS_Toolbox\TestData_0411.gdb\HU12'
    zone_field = 'ZoneID'
    in_value_raster = r'C:\Users\smithn78\PycharmProjects\LAGOS_GIS_Toolbox\TestData_0411.gdb\Total_Nitrogen_Deposition_2006'
    out_table =  r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb\test_zonal_stats_metadata'
    is_thematic = False
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)

if __name__ == '__main__':
    main()
