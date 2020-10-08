import arcpy
from arcpy import management as DM
import master_gdb_tasks
import csiutils
from NHDNetwork import NHDNetwork

LAND_BORDER =  r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\NonPublished\Derived_Land_Borders'
COASTLINE = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\NonPublished\TIGER_Coastline'
STATES_GEO = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Spatial_Classifications\state'
MASTER_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Lakes\LAGOS_US_All_Lakes_1ha'

# ---POSTPROCESSING FUNCTIONS-------------------------------------------------------------------------------------------
def calc_watershed_equality(interlake_watershed_fc, network_watershed_fc):
    """Tests whether the interlake and network watersheds are equal and stores result in a flag field for each fc."""
    try:
        DM.AddField(interlake_watershed_fc, 'equalsnws', 'TEXT', field_length=1)
    except:
        pass
    try:
        DM.AddField(network_watershed_fc, 'equalsiws', 'TEXT', field_length=1)
    except:
        pass
    iws_area = {r[0]: r[1] for r in
                arcpy.da.SearchCursor(interlake_watershed_fc, ['Permanent_Identifier', 'SHAPE@area'])}
    net_area = {r[0]: r[1] for r in arcpy.da.SearchCursor(network_watershed_fc, ['Permanent_Identifier', 'SHAPE@area'])}
    with arcpy.da.UpdateCursor(interlake_watershed_fc, ['Permanent_Identifier', 'equalsnws']) as u_cursor:
        for row in u_cursor:
            permid, flag = row
            if permid in iws_area and permid in net_area:
                area_is_diff = abs(iws_area[permid] - net_area[permid]) >= 10  # meters square, or 0.01 hectares
                flag = 'N' if area_is_diff else 'Y'
            u_cursor.updateRow((permid, flag))
    with arcpy.da.UpdateCursor(network_watershed_fc, ['Permanent_Identifier', 'equalsiws']) as u_cursor:
        for row in u_cursor:
            permid, flag = row
            if permid in iws_area and permid in net_area:
                area_is_diff = abs(iws_area[permid] - net_area[permid]) >= 10  # square meters
                flag = 'N' if area_is_diff else 'Y'
            u_cursor.updateRow((permid, flag))


def calc_watershed_subtype(nhd_gdb, interlake_fc, fits_naming_standard=True):
    if fits_naming_standard:
        permid = 'ws_permanent_identifier'
        eq = 'ws_equalsnws'
        vpuid = 'ws_vpuid'

    else:
        permid = 'Permanent_Identifier'
        eq = 'equalsnetwork'
        vpuid = 'VPUID'

    # Get list of eligible lakes
    nhd_network = NHDNetwork(nhd_gdb)
    gdb_wb_permids = {row[0] for row in arcpy.da.SearchCursor(nhd_network.waterbody, 'Permanent_Identifier') if row[0]}
    eligible_lake_ids = {row[0] for row in arcpy.da.SearchCursor(interlake_fc, permid)}
    matching_ids = list(gdb_wb_permids.intersection(eligible_lake_ids))

    matching_ids_query = '{} IN ({})'.format(permid, ','.join(['\'{}\''.format(id) for id in matching_ids]))
    interlake_fc_mem = arcpy.Select_analysis(interlake_fc, 'in_memory/interlake_fc', matching_ids_query)

    # Pick up watershed equality flag
    print('Reading equality flag...')
    try:
        equalsnetwork = {r[0]: r[1] for r in arcpy.da.SearchCursor(interlake_fc_mem, [permid, eq])}
    except:
        print('Run the watershed_equality function to calculate the equalsnetwork flag before using this tool.')
        raise

    # Run traces
    print('Tracing...')
    nhd_network.set_start_ids(matching_ids)
    traces = nhd_network.trace_up_from_waterbody_starts()

    # Step 4: Calculate sub-types

    def label_subtype(id, trace, equalsnetwork):
        inside_ids = nhd_network.waterbody_flowline[id]
        inside_ids.append(id)
        nonself_trace_up = set(trace).difference(set(inside_ids))
        if not nonself_trace_up:
            return 'LC'
        elif equalsnetwork == 'N':
            return 'IDWS'
        else:
            return 'DWS'

    print('Saving results...')
    subtype_results = {k: label_subtype(k, v, equalsnetwork[k]) for k, v in traces.items()}

    if not arcpy.ListFields(interlake_fc, 'ws_subtype'):
        DM.AddField(interlake_fc, 'ws_subtype', 'TEXT', field_length=4)

    with arcpy.da.UpdateCursor(interlake_fc, [permid, vpuid, 'ws_subtype'], matching_ids_query) as u_cursor:
        for row in u_cursor:
            new_result = subtype_results[row[0]]
            vpuid_val = row[1]
            if vpuid_val == nhd_network.huc4:  # only update if the catchment came from the corresponding VPUID
                row[2] = new_result
            u_cursor.updateRow(row)

    DM.Delete('in_memory/interlake_fc')
    return (subtype_results)

# Not called anymore
def qa_shape_metrics(interlake_watershed_fc, network_watershed_fc, lakes_fc):
    for fc in [interlake_watershed_fc, network_watershed_fc]:
        try:
            DM.AddField(fc, 'isoperimetric', 'DOUBLE')
        except:
            pass
        try:
            DM.AddField(fc, 'perim_area_ratio', 'DOUBLE')
        except:
            pass
        try:
            DM.AddField(fc, 'lake_shed_area_ratio', 'DOUBLE')
        except:
            pass
        lake_areas = {r[0]: r[1] for r in
                      arcpy.da.SearchCursor(lakes_fc, ['Permanent_Identifier', 'lake_waterarea_ha'])}
        with arcpy.da.UpdateCursor(fc, ['isoperimetric', 'perim_area_ratio',
                                        'lake_shed_area_ratio', 'Permanent_Identifier', 'SHAPE@']) as u_cursor:
            for row in u_cursor:
                iso, pa, lakeshed, id, shape = row
                iso = (4 * 3.14159 * shape.area) / (shape.length ** 2)
                pa = shape.length / shape.area
                lakeshed = lake_areas[id] * 10000 / shape.area  # convert lake area to m2
                u_cursor.updateRow((iso, pa, lakeshed, id, shape))


# ---MAIN FUNCTION------------------------------------------------------------------------------------------------------
def process_ws(sheds_fc, zone_name, network_fc ='', nhd_gdb='', fits_naming_standard=True):
    """
    Adds a large assortment of LAGOS-defined fields to the watershed delineation feature classes. Works on both
    partial and merged watersheds layers. Constant values LAND_BORDER, COASTLINE, STATES_GEO, MASTER_LAKES are
    workstation dependent.
    :param sheds_fc: The watersheds feature class. Either interlake or network watersheds are accepted.
    :param zone_name: The short name for the zone, either 'ws' or 'nws'.
    :param network_fc: If providing an interlake watershed class, provide a path to the network watersheds.
    :param nhd_gdb: If post-processing a subregion-level dataset, provide a path to the associated NHD geodatabase.
    :param fits_naming_standard: Boolean value indicating whether watersheds feature class fits LAGOS naming standard.
    :return: sheds_fc
    """

    # -------- setup --------
    if zone_name not in ('ws', 'nws'):
        raise Exception("Please use either 'ws' or 'nws' for the zone name.")

    # establish names
    zoneid = '{}_zoneid'.format(zone_name)
    onlandborder = '{}_onlandborder'.format(zone_name)
    oncoast = '{}_oncoast'.format(zone_name)
    inusa_pct = '{}_inusa_pct'.format(zone_name)
    ismultipart = '{}_ismultipart'.format(zone_name)
    focallakewaterarea_ha = '{}_focallakewaterarea_ha'.format(zone_name)
    area_ha = '{}_area_ha'.format(zone_name)
    perimeter_m = '{}_perimeter_m'.format(zone_name)
    lake_arearatio = '{}_lake_arearatio'.format(zone_name)
    mbgconhull_length_m = '{}_mbgconhull_length_m'.format(zone_name)
    mbgconhull_width_m = '{}_mbgconhull_width_m'.format(zone_name)
    mbgconhull_orientation_deg = '{}_mbgconhull_orientation_deg'.format(zone_name)
    meanwidth_m = '{}_meanwidth_m'.format(zone_name)

    # add fields
    print("Adding fields...")
    DM.AddField(sheds_fc, 'lagoslakeid', 'LONG')
    DM.AddField(sheds_fc, zoneid, 'TEXT', field_length = 10)
    DM.AddField(sheds_fc, onlandborder, 'TEXT', field_length = 2)
    DM.AddField(sheds_fc, oncoast, 'TEXT', field_length = 2)
    DM.AddField(sheds_fc, inusa_pct, 'DOUBLE')
    DM.AddField(sheds_fc, ismultipart, 'TEXT', field_length=2)
    if zone_name == 'ws':
        DM.AddField(sheds_fc, 'ws_sliverflag', 'TEXT', field_length = 2)
    DM.AddField(sheds_fc, focallakewaterarea_ha, 'DOUBLE')
    DM.AddField(sheds_fc, area_ha, 'DOUBLE')
    DM.AddField(sheds_fc, perimeter_m, 'DOUBLE')
    DM.AddField(sheds_fc, lake_arearatio, 'DOUBLE')
    DM.AddField(sheds_fc, mbgconhull_length_m, 'DOUBLE')
    DM.AddField(sheds_fc, mbgconhull_width_m, 'DOUBLE')
    DM.AddField(sheds_fc, mbgconhull_orientation_deg, 'DOUBLE')
    DM.AddField(sheds_fc, meanwidth_m, 'DOUBLE')
    # ws_subtype added by its tool
    # ws_equalsnws added by its tool
    # *_states added by its tool

    #------ calculations --------
    # equality and subtype flags
    if zone_name == 'ws':
        calc_watershed_equality(sheds_fc, network_fc)
        calc_watershed_subtype(nhd_gdb, sheds_fc, fits_naming_standard)

    # add lagoslakeid and copy to zoneid
    permid_lagosid = {r[0]: r[1] for r in arcpy.da.SearchCursor(MASTER_LAKES, ['Permanent_Identifier', 'lagoslakeid'])}
    with arcpy.da.UpdateCursor(sheds_fc, ['Permanent_Identifier', 'lagoslakeid']) as u_cursor:
        for row in u_cursor:
            row[1] = permid_lagosid[row[0]]
            u_cursor.updateRow(row)
    DM.CalculateField(sheds_fc, zoneid, '!lagoslakeid!', 'PYTHON')

    # basic area, perim
    print("Calculating shape metrics...")
    lake_area_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(MASTER_LAKES, ['lagoslakeid', 'lake_waterarea_ha'])}
    shape_fields = ['lagoslakeid',
              ismultipart,
              focallakewaterarea_ha,
              area_ha,
              perimeter_m,
              lake_arearatio,
              'SHAPE@']
    with arcpy.da.UpdateCursor(sheds_fc, shape_fields) as u_cursor:
        for row in u_cursor:
            id, multi, lake_area, area, perim, ratio, shape = row
            if shape.isMultipart:
                multi = 'Y'
            else:
                multi = 'N'
            lake_area = lake_area_dict[id]
            area = shape.area / 10000  # convert m to ha
            perim = shape.length  # in correct units already
            ratio = area/lake_area
            row = (id, multi, lake_area, area, perim, ratio, shape)
            u_cursor.updateRow(row)

    print('Adding flags...')
    # add boundary flag fields
    # identify border zones
    sheds_fc_lyr = DM.MakeFeatureLayer(sheds_fc)
    border_lyr = DM.MakeFeatureLayer(LAND_BORDER, 'border_lyr')
    DM.SelectLayerByLocation(sheds_fc_lyr, 'INTERSECT', border_lyr)
    DM.CalculateField(sheds_fc_lyr, onlandborder, "'Y'", 'PYTHON')
    DM.SelectLayerByAttribute(sheds_fc_lyr, 'SWITCH_SELECTION')
    DM.CalculateField(sheds_fc_lyr, onlandborder ,"'N'", 'PYTHON')

    # identify coastal zones
    coastal_lyr = DM.MakeFeatureLayer(COASTLINE, 'coastal_lyr')
    DM.SelectLayerByLocation(sheds_fc_lyr, 'INTERSECT', coastal_lyr)
    DM.CalculateField(sheds_fc_lyr, oncoast, "'Y'", 'PYTHON')
    DM.SelectLayerByAttribute(sheds_fc_lyr, 'SWITCH_SELECTION')
    DM.CalculateField(sheds_fc_lyr, oncoast, "'N'", 'PYTHON')

    # percent in USA
    arcpy.TabulateIntersection_analysis(sheds_fc, zoneid, STATES_GEO, 'in_memory/tabarea')

    # round to 2 digits and don't let values exceed 100
    inusa_dict = {r[0]:min(round(r[1],2), 100)
                  for r in arcpy.da.SearchCursor('in_memory/tabarea', [zoneid, 'PERCENTAGE'])}

    with arcpy.da.UpdateCursor(sheds_fc, [zoneid, inusa_pct]) as u_cursor:
        for row in u_cursor:
            row[1] = inusa_dict[row[0]]
            u_cursor.updateRow(row)

    # assign states to zone
    print('State assignment...')
    master_gdb_tasks.find_states(sheds_fc, STATES_GEO, zone_name)
    # glaciation status
    master_gdb_tasks.calc_glaciation(sheds_fc, zoneid, zone_name)

    # mbgconhull metrics
    print('Adding convex hull metrics...')
    DM.MinimumBoundingGeometry(sheds_fc, 'in_memory/mbg', 'CONVEX_HULL', mbg_fields_option='MBG_FIELDS')
    mbg_dict_fields = ['lagoslakeid',
                       'MBG_Length',
                       'MBG_Width',
                       'MBG_Orientation'
                       ]
    mbg_dict = {r[0]:r[1:] for r in arcpy.da.SearchCursor('in_memory/mbg', mbg_dict_fields)}
    mbg_fields = ['lagoslakeid',
                  mbgconhull_length_m,
                  mbgconhull_width_m,
                  mbgconhull_orientation_deg,
                  area_ha,
                  meanwidth_m]
    with arcpy.da.UpdateCursor(sheds_fc, mbg_fields) as u_cursor:
        for row in u_cursor:
            id, length, width, orientation, area, meanwidth = row
            length, width, orientation = mbg_dict[id]
            meanwidth = area * 10000/length
            row = [id, length, width, orientation, area, meanwidth]
            u_cursor.updateRow(row)

    # set sliverflag to no--the final values of sliverflag are set elsewhere but this is the default value
    if zone_name == 'ws':
        sliver_fields = ['ws_lake_arearatio',
                         'ws_area_ha',
                         'ws_perimeter_m',
                         'ws_sliverflag']
        with arcpy.da.UpdateCursor(sheds_fc, sliver_fields) as u_cursor:
            for row in u_cursor:
                ratio, area_ha, perim, flag = row
                area_m2 = area_ha * 10000
                isoperimetric = (4 * 3.14159 * area_m2)/(perim**2)

                # see LOCUS Guide documentation for ws_sliverflag--table there explains these criteria
                if 0.02 < ratio <= 1.0 and isoperimetric <= 0.003:
                    flag = 'Y'
                elif ratio <= 0.025:
                    flag = 'Y'
                elif 0.025 < ratio <= 0.10 and area_m2 <= 15000:
                    flag = 'Y'
                elif 0.10 < ratio <= 0.13 and area_m2 <= 10000:
                    flag = 'Y'
                elif 0.13 < ratio <= 0.3 and area_m2 <= 5000:
                    flag = 'Y'
                else:
                    flag = 'N'

                row = [ratio, area_ha, perim, flag]
                u_cursor.updateRow(row)

    # rename some more fields
    if fits_naming_standard == False:

        csiutils.rename_field(sheds_fc, 'Permanent_Identifier', '{}_permanent_identifier'.format(zone_name),
                              deleteOld=False)
        csiutils.rename_field(sheds_fc, 'includeshu4inlet', '{}_includeshu4inlet'.format(zone_name), deleteOld=False)
        if arcpy.ListFields(sheds_fc, 'watershedprocess'):
            csiutils.rename_field(sheds_fc, 'watershedprocess', '{}_watershedprocess'.format(zone_name),
                                  deleteOld=False)
            csiutils.rename_field(sheds_fc, 'VPUID', '{}_vpuid'.format(zone_name), deleteOld=False)

        if zone_name == 'ws':
            csiutils.rename_field(sheds_fc, 'equalsnws', 'ws_equalsnws', deleteOld=False)
        if zone_name == 'nws':
            csiutils.rename_field(sheds_fc, 'equalsiws', 'nws_equalsiws', deleteOld=False)

    # cleanup
    for f in ['ORIG_FID', 'Join_Count', 'Target_FID']:
        if arcpy.ListFields(sheds_fc, f):
            DM.DeleteField(sheds_fc, f)
    lyr_objects = [lyr_object for var_name, lyr_object in locals().items() if var_name.endswith('lyr')]
    for l in lyr_objects:
        DM.Delete(l)
    DM.Delete('in_memory/tabarea')
    DM.Delete('in_memory/mbg')

    return(sheds_fc)
