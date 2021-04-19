# filename: watersheds_toolchain.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: code journal (no ArcGIS Toolbox, workstation-specific paths)
# purpose: This code was used to string together the watersheds tools in the correct order for LAGOS, as well as
# manage which subregions would be processed with the NHDPlus-based tools vs with the bare NHD HR tools

from datetime import datetime as dt
from os import path
import os
import subprocess as sp
from time import sleep
from zipfile import ZipFile
import arcpy

import NHDNetwork
from watershed_delineation import aggregate_watersheds, make_gridcode, nhd_plus_watersheds_tools as nt
import lagosGIS

TOOL_ORDER = ('update_grid_codes', 'add_lake_seeds', 'revise_hydrodem', 'fel', 'fdr',
              'delineate_catchments', 'interlake', 'network')

ALT_TOOL_ORDER = ('mosaic_dem', 'burn_dem', 'make_hydrodem', 'make_catseed', 'fdr',
                  'delineate_catchments', 'interlake', 'network')
# Locations of main directories (unique to machine)

# this is the result of the lakes_in_the_us/make_lagos_lakes.py
LAGOS_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.8.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
HU4 = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.8.gdb\Spatial_Classifications\hu4'

# straight as downloaded from web in mid-March 2019
NHDPLUS_ZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution_COMPLETE\Zipped'
NHDPLUS_UNZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution_COMPLETE\Unzipped_Original'
NHD_UNZIPPED_DIR = '' # not using any of these this time, keeping option available in code below
# a directory wherever you want to store the outputs
# each subregion will have its own geodatabase created and saved
OUTPUTS_PARENT_DIR = 'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds_v2_correct'
LOG_FILE = r"D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds_v2_correct\watersheds_log.csv"
# set a scratch workspace: important so that raster.save will work correctly EVERY time in tools
arcpy.env.scratchWorkspace = r'D:\Continental_Limnology\Data_Working\Tool_Execution'

# your 7z path, probably the same
SEVENZ = r'''"C:\Program Files\7-Zip\7z.exe"'''

# ArcGIS map template path
MXD="C:\Program Files (x86)\ArcGIS\Desktop10.3\MapTemplates\Standard Page Sizes\North American (ANSI) Page Sizes\Letter (ANSI A) Portrait.mxd"


class Paths:
    """
    Define job control paths for the 4-digit HUC4.

    :param str huc4: 4-digit HUC4 for the geodatabase to be processed.

    """

    def __init__(self, huc4, hr=True):
        self.huc4 = huc4
        self.hr = hr
        if self.hr:
            self.gdb_zip = path.join(NHDPLUS_ZIPPED_DIR, 'Vectors','NHDPLUS_H_{}_HU4_GDB.zip'.format(huc4))
            self.rasters_zip = path.join(NHDPLUS_ZIPPED_DIR, 'Rasters', 'NHDPLUS_H_{}_HU4_RASTER.7z'.format(huc4))
        else:
            self.gdb = path.join(NHD_UNZIPPED_DIR, 'NHD_H_{}_GDB.gdb'.format(huc4))

        # NHD items that don't exist at start
        if self.hr:
            self.gdb = path.join(NHDPLUS_UNZIPPED_DIR, 'Vectors', 'NHDPLUS_H_{}_HU4_GDB.gdb'.format(huc4))
            self.rasters_dir = path.join(NHDPLUS_UNZIPPED_DIR, 'Rasters', 'HRNHDPlusRasters{}'.format(huc4))
            self.hydrodem = path.join(self.rasters_dir, 'hydrodem.tif')
            self.filldepth = path.join(self.rasters_dir, 'filldepth.tif')
            self.catseed = path.join(self.rasters_dir, 'catseed.tif')
            self.fdr = path.join(self.rasters_dir, 'fdr.tif')
        self.waterbody = path.join(self.gdb, 'NHDWaterbody')
        # output items that don't exist at start
        self.out_dir = OUTPUTS_PARENT_DIR
        self.locate_outputs()

    def locate_outputs(self):
        self.out_gdb = path.join(self.out_dir, 'watersheds_{}.gdb'.format(self.huc4))
        self.lagos_gridcode = path.join(self.out_gdb, 'lagos_gridcode_{}'.format(self.huc4))
        self.lagos_catseed = path.join(self.out_dir, 'catseed', 'lagos_catseed_{}.tif'.format(self.huc4))
        self.lagos_burn = path.join(self.out_dir, 'burn', 'lagos_burn_{}.tif'.format(self.huc4))
        self.lagos_walled = path.join(self.out_dir, 'lagos_burn_{}_walled.tif'.format(self.huc4))
        self.lagos_fel = path.join(self.out_dir, 'hydrodem', 'lagos_hydrodem_{}.tif'.format(self.huc4))
        self.lagos_fdr = path.join(self.out_dir, 'fdr', 'lagos_fdr_{}.tif'.format(self.huc4))
        self.local_catchments = path.join(self.out_gdb, 'lagos_catchments_{}'.format(self.huc4))
        self.sheds_base = path.join(self.out_gdb, 'lagos_watersheds_{}'.format(self.huc4))
        self.iws_sheds = path.join(self.out_gdb, 'lagos_watersheds_{}_interlake'.format(self.huc4))
        self.network_sheds = path.join(self.out_gdb, 'lagos_watersheds_{}_network'.format(self.huc4))

        # alternate workflow only
        self.dem = path.join(self.out_dir,'NED13_{}.tif'.format(self.huc4))

    def exist(self):
        """Check whether NHDPlus data available locally in order to proceed."""
        return path.exists(self.gdb_zip) and path.exists(self.rasters_zip)

    def test_zips(self):
        """Return logical indicating whether initial paths exist."""
        test_gdb = ZipFile(self.gdb_zip, 'r').testzip()
        if test_gdb:
            print('{} has a bad file: {}'.format(self.gdb_zip, test_gdb))

        sevenz_cmd = '{} t {}'.format(SEVENZ, self.rasters_zip)
        print sevenz_cmd
        test_raster = sp.call(sevenz_cmd)

        # supposedly 7-zip returns 2 if the archive is invalid
        if test_gdb or test_raster > 0:
            return False
        else:
            return True

    def unzip(self):
        if not path.exists(self.gdb):
            with ZipFile(self.gdb_zip, 'r') as z:
                z.extractall(NHDPLUS_UNZIPPED_DIR)

        if not path.exists(self.rasters_dir):
            os.mkdir(self.rasters_dir)

        if not path.exists(self.catseed):
            sevenz_cmd = '{} e {} -o{} catseed.* filldepth.* hydrodem* -r'.format(SEVENZ, self.rasters_zip, self.rasters_dir)
            sz_result = sp.call(sevenz_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
            if sz_result > 0:
                print("Problem with 7-zip. Error code {}".format(sz_result.returncode))

    def log(self, file, error_msg='', time=0):
        """Format a comma-separated line for recording paths to logging file."""
        items = [self.huc4,
                 self.hr,
                 self.gdb_zip,
                 self.rasters_zip,
                 'NHDWaterbody; catseed.tif; filldepth.tif; hydrodem.tif',
                 LAGOS_LAKES,
                 self.lagos_gridcode,
                 self.lagos_catseed,
                 self.local_catchments,
                 self.iws_sheds,
                 self.network_sheds,
                 'add_waterbody_nhdpid(); update_grid_codes(); add_lake_seeds(); delineate_catchments();',
                 dt.now(),
                 error_msg,
                 time]
        line = ','.join([str(i) for i in items]) + '\n'
        with open(file, 'a') as file:
            file.write(line)

def run(huc4, last_tool='network', wait = False, burn_override=False):
    paths = Paths(huc4)
    arcpy.AddMessage("********STARTING SUBREGION {}...".format(paths.huc4))
    if last_tool:
        stop_index = TOOL_ORDER.index(last_tool)
    # Check that we have the data, otherwise skip
    if not paths.exist():
        raise Exception("NHDPlus HR paths do not exist on local machine.")

    if not path.exists(paths.out_dir):
        os.mkdir(paths.out_dir)
    if not path.exists(paths.out_gdb):
        arcpy.CreateFileGDB_management(path.dirname(paths.out_gdb), path.basename(paths.out_gdb))

    start_time = dt.now()

    if not path.exists(paths.catseed) or not path.exists(paths.gdb):
        arcpy.AddMessage('Unzipping started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        paths.unzip()

    # If the tool output doesn't exist yet, and the job control agrees it should be run, try running.
    # If the tool fails, continue after logging the error to the CSV.

    tool_count = 0
    # add_waterbody_nhdpid
    if not arcpy.Exists(paths.lagos_gridcode) and stop_index >= 0:
        arcpy.AddMessage('Adding NHDPlusIDs to waterbodies started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.add_waterbody_nhdpid(paths.waterbody, LAGOS_LAKES)
        tool_count +=1

    # update_grid_codes
    if not arcpy.Exists(paths.lagos_gridcode) and stop_index >= 0:
        arcpy.AddMessage('Updating grid codes started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.update_grid_codes(paths.gdb, paths.lagos_gridcode)
        tool_count += 1

    # add_lake_seeds
    if not arcpy.Exists(paths.lagos_catseed) and stop_index >= 1:
        arcpy.AddMessage('Adding lake seeds started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.add_lake_seeds(paths.catseed, paths.gdb, paths.lagos_gridcode, LAGOS_LAKES, paths.lagos_catseed)
        tool_count += 1

    # revise_hydrodem
    if not arcpy.Exists(paths.lagos_burn) \
            and stop_index >= 2 \
            and not arcpy.Exists(paths.network_sheds) \
            and not burn_override:
        arcpy.AddMessage('Revising hydrodem burn started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.revise_hydrodem(paths.gdb, paths.hydrodem, paths.filldepth, paths.lagos_catseed, paths.lagos_burn)
        tool_count += 1
    if not wait:
        # can't delete with wait on because more than one process might be using in_memory?
        arcpy.Delete_management('in_memory')

    # fill
    if not arcpy.Exists(paths.lagos_fel) and stop_index >= 3:
        pit_start = dt.now()
        arcpy.AddMessage(
            'Pit Remove started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        pitremove_cmd = 'mpiexec -n 8 pitremove -z {} -fel {}'.format(paths.lagos_burn, paths.lagos_fel)
        print pitremove_cmd
        sp.call(pitremove_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
        tool_count += 1
        pit_diff = dt.now() - pit_start
        arcpy.AddMessage('Pit Remove finished in {} seconds'.format(pit_diff.seconds))

    # fdr
    if not arcpy.Exists(paths.lagos_fdr) and stop_index >= 4:
        arcpy.CheckOutExtension('Spatial')
        arcpy.AddMessage('Flow direction started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        arcpy.env.extent = paths.lagos_fel
        flow_dir = arcpy.sa.FlowDirection(paths.lagos_fel)
        # enforce same bounds as NHD fdr, so catchments have same HU4 boundary
        flow_dir_clipped = arcpy.sa.Con(arcpy.sa.IsNull(paths.fdr), paths.fdr, flow_dir)
        flow_dir_clipped.save(paths.lagos_fdr)
        arcpy.CheckInExtension('Spatial')
        tool_count += 1

    # delineate_catchments
    if not arcpy.Exists(paths.local_catchments) and stop_index >= 5:
        arcpy.AddMessage('Delineating catchments started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.delineate_catchments(paths.lagos_fdr, paths.lagos_catseed, paths.gdb, paths.lagos_gridcode, paths.local_catchments)
        tool_count += 1

    # interlake watersheds
    if not arcpy.Exists(paths.iws_sheds) and stop_index >= 6:

        # wait for predecessor to exist
        # useful to split this step into 2nd process. in_memory objects won't interfere, should be safe
        if wait:
            cat_exists = arcpy.Exists(paths.local_catchments)
            while not cat_exists:
                sleep(10)
        arcpy.AddMessage(
            'Interlake watersheds started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        aggregate_watersheds.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.iws_sheds, 'interlake')
        tool_count += 1

    # network watersheds
    if not arcpy.Exists(paths.network_sheds) and stop_index >= 7:

        # wait for predecessor to exist
        # useful to split this step into 2nd process. in_memory objects won't interfere, should be safe
        if wait:
            cat_exists = arcpy.Exists(paths.local_catchments)
            while not cat_exists:
                sleep(10)
        arcpy.AddMessage(
            'Network watersheds started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        aggregate_watersheds.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.network_sheds, 'network')
        tool_count += 1

    time_diff = dt.now() - start_time
    print('Completed {} tools for {} in {} minutes'.format(tool_count, huc4, time_diff.seconds/60))
    return tool_count


def make_run_list(master_HU4):
    """Make a run list that will output one huc4 from most regions first, for QA purposes."""
    regions = ['{:02d}'.format(i) for i in range(1,19)]
    subregions = ['{:02d}'.format(i) for i in range(1,31)]
    template = []

    # do first 1 from each region first
    for s in subregions[:1]:
        template.extend(['{}{}'.format(r, s) for r in regions])
    # then go by region after that
    for r in regions:
        template.extend(['{}{}'.format(r, s) for s in subregions[1:]])

    huc4 = [r[0] for r in arcpy.da.SearchCursor(master_HU4, 'hu4_sourceid_huc4')]
    return [i for i in template if i in huc4]


if __name__ == '__main__':
    run_list = make_run_list(HU4)
    great_lakes =['0418', '0420', '0424', '0427', '0429', '0430']
    run_list.extend(great_lakes)
    run_list.sort()
    # big_files = ['0902', '1018', '1109', '1710', '1209', '1304', '1606', '1701', '1702']
    # for bf in big_files:
    #     run_list.remove(bf)
    run_list.remove('0424')
    run_list.remove('0415')


    for huc4 in run_list:
        p = Paths(huc4)
        try:
            last_tool = 'network'
            start_time = dt.now()
            tool_count = run(p.huc4, last_tool, burn_override=True)
            time_diff = dt.now() - start_time
            if tool_count > 0:
                p.log(LOG_FILE, '{}: SUCCESS'.format(last_tool), time_diff.seconds/60)
        except Exception as e:
            p.log(LOG_FILE, repr(e))
            print(e)
        finally:
            arcpy.Delete_management('in_memory')

def patch_on_network_flag():
    """Patch implemented on Apr 17 to allow more outlets per subregion, if several large networks appear."""
    cats = []
    for dirpath, dirnames, filenames in arcpy.da.Walk(OUTPUTS_PARENT_DIR, 'FeatureClass'):
        for fn in filenames:
            if 'lagos_catchments' in fn:
                cats.append(os.path.join(dirpath, fn))
    for cat in cats:
        huc4 = cat[-4:]
        print(huc4)
        p = Paths(huc4)
        nhd_network = NHDNetwork.NHDNetwork(p.gdb)
        on_network = set(nhd_network.trace_up_from_hu4_outlets())
        with arcpy.da.UpdateCursor(cat, ['Permanent_Identifier', 'On_Main_Network']) as u_cursor:
            for row in u_cursor:
                permid, onmain = row
                onmain = 'Y' if permid in on_network else 'N'
                u_cursor.updateRow((permid, onmain))


def add_ws_flags():
    # run_list = make_run_list(HU4)
    run_list  = make_run_list(HU4)
    failures = []
    for huc4 in run_list:
        print(huc4)
        p = Paths(huc4)
        nt.watershed_equality(p.iws_sheds, p.network_sheds)
        nt.qa_shape_metrics(p.iws_sheds, p.network_sheds, LAGOS_LAKES)

def merge_watersheds(parent_directory, output_fc, tag):
    merge_fcs = []
    alt_merge_fcs = []
    walk = arcpy.da.Walk(parent_directory, datatype='FeatureClass')
    for dirpath, dirnames, filenames in walk:
        for filename in filenames:
            if tag in filename and 'alt' not in dirpath:
                merge_fcs.append(os.path.join(dirpath, filename))
            if tag in filename and 'alt' in dirpath and tag == 'catchment':
                alt_merge_fcs.append(os.path.join(dirpath, filename))

    # merge the main results
    if tag == 'catchment' or tag == 'interlake':
        output_fc = lagosGIS.efficient_merge(merge_fcs, output_fc)

    elif tag == 'network':
        output_fc = lagosGIS.efficient_merge(merge_fcs, output_fc, "equalsiws = 'N'")

    # fill in some of the regions where the NHDPlus HR falls short of the HU4 boundary we used along a border where
    # NHDPlus is used on one side and NHD is used on the other

    # These regions cannot be in any lake's watershed but they allow the landscape to be dissected
    if tag == 'catchment':
        MERGE_REGIONS = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\NHD_Combined_Regions'
        for fc in alt_merge_fcs:
            lyr = arcpy.MakeFeatureLayer_management(fc, 'lyr')
            arcpy.SelectLayerByLocation_management(lyr, 'INTERSECT', MERGE_REGIONS)
            arcpy.Append_management(output_fc, lyr)

    return output_fc

def add_subtypes(interlake_fc):
    not_hr = ['0401', '0402', '0403', '0404', '0405', '0406', '0407',
              '0408', '0409', '0410', '0411', '0412', '0413', '0414',
              '0415', '0801', '0802', '0803',
              '0804', '0805', '0806', '0807', '0808', '0809',
              '1802', '1803', '1804', '1805']
    hr = [h for h in make_run_list(HU4) if h not in not_hr]

    for huc4 in hr:
        print(huc4)
        p = Paths(huc4)
        nt.calc_subtype_flag(p.gdb, interlake_fc)
    for huc4 in not_hr:
        print(huc4)
        p = Paths(huc4, hr=False)
        nt.calc_subtype_flag(p.gdb, interlake_fc)


