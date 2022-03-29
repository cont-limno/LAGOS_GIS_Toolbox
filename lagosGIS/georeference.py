# filename: georeference.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LIMNO
# tool type: limited re-usability as code (change constants by hand for your computer)
# purpose: Identify the lakes being sampled with water quality observation data.
# Convert lake sampling data to point features using an appropriate coordinate system and spatially link the
# point features to the best matching LAGOS-US lake polygon, if possible.

import os
import arcpy
from collections import Counter
from arcpy import analysis as AN
from arcpy import management as DM
import lagosGIS

# Features to use for geographic linking.
# Change these to match your computer. It's not very elegant.
MASTER_LAKES_FC = 'NHDWaterbody_LAGOS'  # population of valid lakes
MASTER_LAKES_LINES = 'NHDWaterbody_LAGOS_Line'  # artificial paths associated with lakes in MASTER_LAKES_FC
MASTER_STREAMS_FC = 'NHDArea_LAGOS'  # merged NHDArea polygon features from NHD with StreamRiver feature type
MASTER_XWALK = 'LAGOS_Lake_Link_v1_legacy_only'  # lake identifier crosswalk, see lake_link in LAGOS-US LOCUS

# Can change but probably don't need to
MASTER_LAKE_ID = 'lagoslakeid'
MASTER_GNIS_NAME = "GNIS_Name"
# MASTER_STREAM_ID = 'Permanent_Identifier' #hard-coded below
MASTER_COUNTY_NAME = 'COUNTY_NAME'
MASTER_STATE_NAME = 'STATE'
STATES = ("AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS",
          "KY", "LA", "MA", "MD", "ME", "MH", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV",
          "NY", "OH", "OK", "OR", "PA", "PR", "PW", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VI", "VT", "WA", "WI",
          "WV", "WY"
          )
LAGOSNE_STATES = ("CT", "IA", "IL", "IN", "MA", "ME", "MI", "MN", "MO", "NH", "NJ", "NY", "OH", "PA", "RI", "VT", "WI")
CRS_DICT = {'NAD83': 4269,
            'WGS84': 4326,
            'NAD27': 4267,
            'NAD_1983_StatePlane_Washington_North_FIPS_4601_Feet': 102748,
            'NAD_1983_HARN_UTM_Zone_15N': 3745,
            }


def spatialize_sites(lake_points_csv, out_fc, in_x_field, in_y_field, in_crs='NAD83'):
    """
    Casts xy data as spatial points.
    :param lake_points_csv: The lake water quality dataset containing coordinates as text columns.
    :param out_fc: The output feature class
    :param in_x_field: Field containing the longitude or x coordinates
    :param in_y_field: Field containing the latitude or y coordinates
    :param in_crs: Abbreviation of the coordinate reference system used to specify the coordinates.

    Options supported are 'WGS84', 'NAD83', 'NAD27.
    :return: The output feature class
    """

    if in_crs not in CRS_DICT.keys():
        raise ValueError('Use one of the following CRS names: {}'.format(','.join(CRS_DICT.keys())))
    DM.MakeXYEventLayer(lake_points_csv, in_x_field, in_y_field, 'xylayer', arcpy.SpatialReference(CRS_DICT[in_crs]))
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    DM.CopyFeatures('xylayer', out_fc)
    arcpy.Delete_management('xylayer')
    return out_fc


def georeference_lake_sites(sample_sites_point_fc, out_fc, site_id_field,
                            lake_name_field, lake_county_field='', state='',
                            master_gdb=r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\Lake_Georeferencing\Masters_for_georef.gdb'
                            ):
    """
    Evaluate water quality sampling point locations and either assign the point to a lake polygon or flag the
    point for manual review. This function is meant to be used as the first of two steps in a semi-automated linking
    process, in which a possible linked lake for each site is calculated and then a reviewer visually inspects each
    site in context with corroborating information in order to accept or reject the links.
    :param sample_sites_point_fc: A point feature class containing water quality sampling data (see spatialize_sites)
    :param out_fc: An output feature class to save the result to
    :param site_id_field: The column/field determined by the user to be the unique identifier associated with one
    or more observations at a single location (i.e. a "site"). If a lake can have multiple sites in the dataset,
    choose the "site" identifier, not the lake identifier.
    :param lake_name_field: The lake name recorded with the observation
    :param lake_county_field: (Optional) The county name recorded with the observation, if available, which will be
    used to limit name-based matches to lakes in the same county to avoid mis-identifying lakes with common names
    :param state: (Optional) The 2-letter abbreviation of the U.S. state the dataset is limited to
    :param master_gdb: Location of master geodatabase used for linking that contains the collateral matching information
    described in the variables MASTER_LAKES_FC, MASTER_LAKES_LINES, MASTER_STREAMS_FC, and MASTER_XWALK in this script
    :return: A point feature class containing the original input rows with the following fields added to document and
    control the semi-automated linking process.
        -Auto_Comment: Match status of site suggested by georeference_lakes. Permitted values:
            'Exact location link'
            'Linked by common name and location'
            'Linked by common location'
            'Not linked because represented as river in NHD'
            'LAGOS-NE legacy link'
            'Not linked"
        -Comment: Match status of site finalized after review. (Edit this field during review.)
        -Manual_Review: Numeric value indicating level of scrutiny to apply to suggested link, with higher values
        indicating matches with less confidence.
        -Shared_Words: Lake name elements common to the site and the linked lake
        -Linked_lagoslakeid: The lagoslakeid for the LAGOS-US lake polygon linked to the sampling site. (Edit this field
        during review.)
        -GEO_Discovered_Name: A column to add any additional names for the lake discovered during lake linking review.
        -Duplicate_Candidate: A Y/N flag indicating whether multiple suggested links are included in the dataset (Delete
        one of the rows after choosing the best one in manual review.)
        -Is_Legacy_Link: A Y/N flag indicating whether the site identifier was detected in the LAGOS-NE legacy site
        identifiers list provided in the LAGOS-US lake_link crosswalk.
        -Total_points_in_lake_poly: The number of unique site identifiers suggested to be linked to the same LAGOS-US
        lake as this site, including this site in the count.
        -Note: A field provided for any free-form notes and comments about linking determinations during manual review.
    """

    # ---SETUP----------------------------------------------------------------------------------------------------
    master_lakes_fc = os.path.join(master_gdb, MASTER_LAKES_FC)
    master_lakes_lines = os.path.join(master_gdb, MASTER_LAKES_LINES)
    master_streams_fc = os.path.join(master_gdb, MASTER_STREAMS_FC)
    master_xwalk = os.path.join(master_gdb, MASTER_XWALK)

    state = state.upper()
    if state not in STATES:
        raise ValueError('Use the 2-letter state code abbreviation')
    arcpy.env.workspace = 'in_memory'
    out_short = os.path.splitext(os.path.basename(out_fc))[0]
    join1 = '{}_1'.format(out_short)
    join2 = '{}_2'.format(out_short)
    join3 = '{}_3'.format(out_short)
    join4 = '{}_4'.format(out_short)
    point_fields = [f.name for f in arcpy.ListFields(sample_sites_point_fc)]

    # If the lake ID is not a text/string value type, change to string
    lake_id_field_type = arcpy.ListFields(sample_sites_point_fc, site_id_field)[0].type
    if lake_id_field_type != 'String':
        temp_id_field = '{}_t'.format(site_id_field)
        arcpy.AddField_management(sample_sites_point_fc, '{}_t'.format(site_id_field), 'TEXT', '255')
        expr = '!{}!'.format(site_id_field)
        arcpy.CalculateField_management(sample_sites_point_fc, temp_id_field, expr, 'PYTHON')
        arcpy.DeleteField_management(sample_sites_point_fc, site_id_field)
        arcpy.AlterField_management(sample_sites_point_fc, temp_id_field, new_field_name=site_id_field)

    # ---SPATIAL LINK EVIDENCE GATHERING ----------------------------------------------------------------------
    # Perform joins to gather spatial link information to apply rules later
    # Join 1: point inside lake
    # Join 2: point inside double-banked stream polygon (not lake)
    # Join 3: point within 10m of lake border
    # Join 4: point within 100m of lake border
    join1 = AN.SpatialJoin(sample_sites_point_fc, master_lakes_fc, join1, 'JOIN_ONE_TO_MANY', 'KEEP_ALL',
                           match_option='INTERSECT')
    join2 = AN.SpatialJoin(join1, master_streams_fc, join2, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option='INTERSECT')
    join3 = AN.SpatialJoin(join2, master_lakes_fc, join3, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option='INTERSECT',
                           search_radius='10 meters')
    join4 = AN.SpatialJoin(join3, master_lakes_fc, join4, 'JOIN_ONE_TO_MANY', 'KEEP_ALL', match_option='INTERSECT',
                           search_radius='100 meters')

    # ---APPLY DISTANCE & NAME-BASED LOGIC TO CHOOSE LINK---------------------------------------------------------
    # Set-up for editing lake assignment values
    DM.AddField(join4, 'Auto_Comment', 'TEXT', field_length=100)
    DM.AddField(join4, 'Manual_Review', 'SHORT')
    DM.AddField(join4, 'Shared_Words', 'TEXT', field_length=100)
    DM.AddField(join4, 'Linked_lagoslakeid', 'LONG')
    DM.AddField(join4, 'GEO_Discovered_Name', 'TEXT', field_length=255)
    DM.AddField(join4, 'Duplicate_Candidate', 'TEXT', field_length=1)
    DM.AddField(join4, 'Is_Legacy_Link', 'TEXT', field_length=1)
    update_fields = [site_id_field,
                     lake_name_field,
                     MASTER_LAKE_ID,
                     MASTER_GNIS_NAME,  # 0m match
                     'PERMANENT_IDENTIFIER_1', 'GNIS_NAME_1',  # stream match
                     MASTER_LAKE_ID + '_1', MASTER_GNIS_NAME + '_12',  # 10m match
                     MASTER_LAKE_ID + '_12', MASTER_GNIS_NAME + '_12_13',  # 100m match
                     'Auto_Comment',
                     'Manual_Review',
                     'Shared_Words',
                     'Linked_lagoslakeid']

    # Evaluate match criteria for each lake and transfer the linked lagoslakeid value to the Linked_lagoslakeid field
    # if the match is accepted.
    # Update the comment to describe the match type.
    # Update the manual review flag to indicate only superficial review needed (-1) for convincing matches, and review
    # needed (>=1, higher values need more scrutiny) if the match is less convincing or needs discrimination
    # These criteria flow from most convincing (inside lake) to least convincing link.
    cursor = arcpy.da.UpdateCursor(join4, update_fields)
    arcpy.AddMessage("Calculating link status...")
    for row in cursor:
        id, name, mid_0, mname_0, stream_id, streamname_0, mid_10, mname_10, mid_100, mname_100, comment, review, words, lagosid = row
        if mid_0 is not None:  # if the point is directly in a polygon
            if name and mname_0:
                words = lagosGIS.list_shared_words(name, mname_0, exclude_lake_words=False)
            comment = 'Exact location link'
            lagosid = mid_0
            review = -1
        elif mid_0 is None and mid_10 is not None:  # if the point is only within 10m of a lake
            if name and mname_10:
                words = lagosGIS.list_shared_words(name, mname_10, exclude_lake_words=False)
            if words:
                comment = 'Linked by common name and location'
                lagosid = mid_10
                review = -1
            else:
                comment = 'Linked by common location'
                lagosid = mid_10
                review = 1
        elif mid_0 is None and mid_10 is None:
            if stream_id is not None:  # if there is a stream match
                comment = 'Not linked because represented as river in NHD'
                review = 2
            else:
                if mid_100 is not None:  # if the point is only within 100m of lake(s)
                    if name and mname_100:
                        words = lagosGIS.list_shared_words(name, mname_100, exclude_lake_words=True)
                    if words:
                        comment = 'Linked by common name and location'
                        lagosid = mid_100
                        review = 1
                    else:
                        comment = 'Linked by common location'
                        lagosid = mid_100
                        review = 2
        cursor.updateRow((id, name, mid_0, mname_0, stream_id, streamname_0, mid_10, mname_10, mid_100, mname_100,
                          comment, review, words, lagosid))

    # --- LEGACY LINKING TO LAGOS-NE IDENTIFIERS-------------------------------------------------------------------
    # If the dataset is from a state that was in LAGOS-NE, flag site for manual review if the match type above was
    # not 'Exact location link' and transfer the lake info that was linked previously for LAGOS-NE (so that sites
    # already matched in LAGOS-NE are not forgotten or over-written by this process for LAGOS-US)
    if state in LAGOSNE_STATES:
        DM.JoinField(join4, site_id_field, master_xwalk, 'lagosne_legacyid',
                     ['lagoslakeid', 'lagos_lakename', 'lagos_state'])
        update_fields = [site_id_field, lake_name_field,
                         MASTER_LAKE_ID + '_12_13', 'lagos_lakename', 'lagos_state',  # crosswalk match
                         'Auto_Comment', 'Manual_Review', 'Shared_Words',
                         'Linked_lagoslakeid', 'Is_Legacy_Link']

        with arcpy.da.UpdateCursor(join4, update_fields) as uCursor:
            for uRow in uCursor:
                id, name, mid_x, mname_x, state_x, comment, review, words, lagosid, legacy_flag = uRow
                # fields are populated already from links above. Revise only if legacy links
                if mid_x is not None:
                    if state == state_x:
                        legacy_flag = 'Y'  # set to Y regardless of whether using legacy comment if state matches
                    if comment != 'Exact location link':
                        review = 1
                        if state != state_x:
                            review = 3  # downgrade if states mismatch--border lakes OK, random common IDs NOT. Check.
                        legacy_flag = 'Y'
                        comment = 'LAGOS-NE legacy link'  # only comment non-exact location matches
                        lagosid = mid_x
                        if name and mname_x:
                            words = lagosGIS.list_shared_words(name, mname_x)  # update words only if legacy comment

                new_row = id, name, mid_x, mname_x, state_x, comment, review, words, lagosid, legacy_flag
                uCursor.updateRow(new_row)

    # ---ASSIGN REVIEW FLAGS FOR EXTREMES--------------------------------------------------------------------------
    # No match
    # Assign high scrutiny, assign and/or copy the no-match comment
    if arcpy.ListFields(join4, 'Comment'):
        comment_field_name = 'Comment_LAGOS'
    else:
        comment_field_name = 'Comment'

    DM.AddField(join4, comment_field_name, 'TEXT', field_length=100)
    with arcpy.da.UpdateCursor(join4, ['Manual_Review', 'Auto_Comment', 'Comment']) as cursor:
        for flag, ac, comment in cursor:
            if flag is None:
                flag = 3
                ac = 'Not linked'
            comment = ac
            cursor.updateRow((flag, ac, comment))

    # Assign lowest scrutiny value for points more than 100m inside lake, very convincing match
    DM.MakeFeatureLayer(join4, 'join5_lyr')
    DM.MakeFeatureLayer(master_lakes_lines, 'lake_lines_lyr')
    DM.SelectLayerByAttribute('join5_lyr', 'NEW_SELECTION', "Auto_Comment = 'Exact location link'")
    DM.SelectLayerByLocation('join5_lyr', 'INTERSECT', 'lake_lines_lyr', '100 meters', 'SUBSET_SELECTION', 'INVERT')
    DM.CalculateField('join5_lyr', 'Manual_Review', '-2', 'PYTHON')
    DM.Delete('join5_lyr', 'lake_lines_lyr')

    # Then make sure to only keep the fields necessary when you write to an output
    copy_fields = point_fields + ['Linked_lagoslakeid', 'Auto_Comment', 'Manual_Review',
                                  'Is_Legacy_Link',
                                  'Shared_Words', 'Comment', 'Duplicate_Candidate',
                                  'GEO_Discovered_Name']
    copy_fields.remove('Shape')
    copy_fields.remove('OBJECTID')

    lagosGIS.select_fields(join4, out_fc, copy_fields)
    DM.AssignDomainToField(out_fc, 'Comment', 'Comment')  # prevent manual editor from entering bad comments

    # ---MANAGE ONE-TO-MANY SCENARIOS------------------------------------------------------------------------------

    # Remove any duplicates on all non-OID fields.
    # (These originate from the join3/join4 transition because a point can be both
    # within 10m and 100m of lakes, this code takes the closest lake as true for my current sanity.
    # Or, in other words, this is a hack solution.)
    out_fc_fields = [f.name for f in arcpy.ListFields(out_fc) if f.name != 'OBJECTID']
    DM.DeleteIdentical(out_fc, out_fc_fields)

    # Get the join_count for each limno lake ID
    # De-dupe anything resulting from limno ID duplicates first before counting
    id_pairs = list(set(arcpy.da.SearchCursor(out_fc, [site_id_field, 'Linked_lagoslakeid'])))
    # THEN pull out LAGOS id. Any duplicate now are only due to multiple distinct points within lake
    lagos_ids = [ids[1] for ids in id_pairs]
    sample_ids = [ids[0] for ids in id_pairs]
    lagos_lake_counts = Counter(lagos_ids)
    linked_multiple_lake_counts = Counter(sample_ids)

    # Get the count of points in the polygon
    DM.AddField(out_fc, 'Total_points_in_lake_poly', 'Short')
    with arcpy.da.UpdateCursor(out_fc, ['Linked_lagoslakeid', 'Total_points_in_lake_poly']) as cursor:
        for lagos_id, join_count in cursor:
            join_count = lagos_lake_counts[lagos_id]
            cursor.updateRow((lagos_id, join_count))

    # Mark any samples linked to more than one lake so that the analyst can select the correct lake in the
    # manual process
    with arcpy.da.UpdateCursor(out_fc, [site_id_field, 'Duplicate_Candidate']) as cursor:
        for sample_id, duplicate_flag in cursor:
            duplicate_count = linked_multiple_lake_counts[sample_id]
            if duplicate_count > 1:
                duplicate_flag = "Y"
            else:
                duplicate_flag = "N"
            cursor.updateRow((sample_id, duplicate_flag))

    # Cleanup
    DM.AddField(out_fc, 'Note', 'TEXT', field_length=140)
    DM.Delete('in_memory')

    return out_fc