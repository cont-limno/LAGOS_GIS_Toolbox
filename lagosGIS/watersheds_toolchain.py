from datetime import datetime as dt
from os import path
import os
import subprocess as sp
from time import sleep
from zipfile import ZipFile
import arcpy
import nhdplushr_tools as nt
import lagosGIS

TOOL_ORDER = ('update_grid_codes', 'add_lake_seeds', 'fix_hydrodem', 'fel', 'fdr',
              'delineate_catchments', 'interlake', 'network')

ALT_TOOL_ORDER = ('mosaic_dem', 'burn_dem', 'make_hydrodem', 'make_catseed', 'fdr',
                  'delineate_catchments', 'interlake', 'network')
# Locations of main directories (unique to machine)

# this is the result of the lakes_in_the_us/doit.py
LAGOS_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
HU4 = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.5.gdb\Spatial_Classifications\hu4'

# straight as downloaded from web in mid-March 2019
NHDPLUS_ZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution\Zipped'
NHDPLUS_UNZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution\Unzipped_Original'

NHD_UNZIPPED_DIR = 'D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original'

# a directory wherever you want to store the outputs
# each subregion will have its own geodatabase created and saved
OUTPUTS_PARENT_DIR = 'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds'

# set a scratch workspace: important so that raster.save will work correctly EVERY time in tools
arcpy.env.scratchWorkspace = r'D:\Continental_Limnology\Data_Working\Tool_Execution'

# your 7z path, probably the same
SEVENZ = r'''"C:\Program Files\7-Zip\7z.exe"'''

# ArcGIS map template path
MXD = "C:\Program Files (x86)\ArcGIS\Desktop10.3\MapTemplates\Standard Page Sizes\North American (ANSI) Page Sizes\Letter (ANSI A) Portrait.mxd"

class Paths:
    """
    Define job control paths for the 4-digit HUC4.

    :param str huc4: 4-digit HUC4 for the geodatabase to be processed.

    """

    def __init__(self, huc4, hr=True):
        self.huc4 = huc4
        self.hr = hr
        if self.hr:
            self.gdb_zip = path.join(NHDPLUS_ZIPPED_DIR, 'NHDPLUS_H_{}_HU4_GDB.zip'.format(huc4))
            self.rasters_zip = path.join(NHDPLUS_ZIPPED_DIR, 'NHDPLUS_H_{}_HU4_RASTER.7z'.format(huc4))
        else:
            self.gdb = path.join(NHD_UNZIPPED_DIR, 'NHD_H_{}_GDB.gdb'.format(huc4))

        # NHD items that don't exist at start
        if self.hr:
            self.gdb = path.join(NHDPLUS_UNZIPPED_DIR, 'NHDPLUS_H_{}_HU4_GDB.gdb'.format(huc4))
            self.rasters_dir = path.join(NHDPLUS_UNZIPPED_DIR, 'HRNHDPlusRasters{}'.format(huc4))
            self.hydrodem = path.join(self.rasters_dir, 'hydrodem.tif')
            self.catseed = path.join(self.rasters_dir, 'catseed.tif')
            self.fdr = path.join(self.rasters_dir, 'fdr.tif')
        self.waterbody = path.join(self.gdb, 'NHDWaterbody')
        # output items that don't exist at start
        self.out_dir = path.join(OUTPUTS_PARENT_DIR, 'watersheds_{}'.format(huc4))
        self.locate_outputs()

    def locate_outputs(self):
        self.out_gdb = path.join(self.out_dir, 'watersheds_{}.gdb'.format(self.huc4))
        self.lagos_gridcode = path.join(self.out_gdb, 'lagos_gridcode_{}'.format(self.huc4))
        self.lagos_catseed = path.join(self.out_dir, 'lagos_catseed_{}.tif'.format(self.huc4))
        self.lagos_burn = path.join(self.out_dir, 'lagos_burn_{}.tif'.format(self.huc4))
        self.lagos_walled = path.join(self.out_dir, 'lagos_burn_{}_walled.tif'.format(self.huc4))
        self.lagos_fel = path.join(self.out_dir, 'lagos_hydrodem_{}_fel.tif'.format(self.huc4))
        self.lagos_fdr = path.join(self.out_dir, 'lagos_fdr_{}.tif'.format(self.huc4))
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
            sevenz_cmd = '{} e {} -o{} catseed.* fdr.* hydrodem* -r'.format(SEVENZ, self.rasters_zip, self.rasters_dir)
            sz_result = sp.call(sevenz_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
            if sz_result > 0:
                print("Problem with 7-zip. Error code {}".format(sz_result.returncode))

    def log(self, file, error_msg=''):
        """Format a comma-separated line for recording paths to logging file."""
        items = [self.huc4,
                 self.hr,
                 self.gdb_zip,
                 self.rasters_zip,
                 'NHDWaterbody; catseed.tif; fdr.tif',
                 LAGOS_LAKES,
                 self.lagos_gridcode,
                 self.lagos_catseed,
                 self.local_catchments,
                 self.iws_sheds,
                 self.network_sheds,
                 'add_waterbody_nhdpid(); update_grid_codes(); add_lake_seeds(); delineate_catchments();',
                 error_msg]
        line = ','.join([str(i) for i in items]) + '\n'
        with open(file, 'a') as file:
            file.write(line)

    # def photograph(self, overwrite=False):
    #     if not path.exists(self.out_dir):
    #         os.mkdir(self.out_dir)
    #     hmin = float(arcpy.GetRasterProperties_management(self.hydrodem, 'MINIMUM').getOutput(0))
    #     hmax = float(arcpy.GetRasterProperties_management(self.hydrodem, 'MAXIMUM').getOutput(0)) - 500000
    #
    #     vals = {self.catseed:[0, 1, -32768, 50, 50],
    #             self.fdr: [0, 128, 255, 25, 25],
    #             self.hydrodem: [hmin, hmax, -2147483648, 50, 50],
    #             self.lagos_catseed: [0, 1, -32768, 50, 50],
    #             self.lagos_fdr: [0, 128, 255, 25, 25],
    #             self.lagos_fel: [hmin, hmax, -2147483648, 50, 50]
    #             }
    #     for tif, values in vals.items():
    #         jpg = path.join(self.out_dir, '{}_{}.jpg'.format(path.splitext(path.basename(tif))[0], self.huc4))
    #         if overwrite or not path.exists(jpg):
    #             gdal_cmd = 'gdal_translate -a_nodata {} -of JPEG -co worldfile=yes -b 1 -b 1 -b 1 -scale {} {} 0 255 -outsize {}% {}% {} {}'.\
    #                 format(values[2], values[0], values[1], values[3], values[4], tif, jpg)
    #             sp.call(gdal_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)


def run(huc4, last_tool='network', wait = False, burn_override=True):
    paths = Paths(huc4)
    arcpy.AddMessage("Starting subregion {}...".format(paths.huc4))
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

    # fix_hydrodem
    if not arcpy.Exists(paths.lagos_burn) \
            and stop_index >= 2 \
            and not arcpy.Exists(paths.network_sheds)\
            and not burn_override:
        arcpy.AddMessage('Fixing hydrodem burn started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        nt.fix_hydrodem(paths.hydrodem, paths.lagos_catseed, paths.lagos_burn)
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
        flow_dir = arcpy.sa.FlowDirection(paths.lagos_fel)
        # enforce same bounds as NHD fdr, so catchments have same HU4 boundary
        # TODO: For non-hr, clip to HU4 instead
        print(arcpy.Describe(flow_dir).spatialReference.name)
        print(arcpy.Describe(paths.fdr).spatialReference.name)
        print(arcpy.Describe(flow_dir).extent)
        print(arcpy.Describe(paths.fdr).extent)
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
        nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.iws_sheds, 'interlake')
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
        nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.network_sheds, 'network')
        tool_count += 1

    time_diff = dt.now() - start_time
    print('Completed {} tools for {} in {} minutes'.format(tool_count, huc4, time_diff.seconds/60))
    return tool_count


def make_run_list(master_HU4):
    """Make a run list that will output one huc4 from most regions first, for QA purposes."""
    regions = ['{:02d}'.format(i) for i in range(1,19)]
    subregions = ['{:02d}'.format(i) for i in range(1,31)]
    template = []

    # do first 2 from each region first
    for s in subregions[:2]:
        template.extend(['{}{}'.format(r, s) for r in regions])
    # then go by region after that
    for r in regions:
        template.extend(['{}{}'.format(r, s) for s in subregions[2:]])

    huc4 = [r[0] for r in arcpy.da.SearchCursor(master_HU4, 'hu4_huc4')]
    return [i for i in template if i in huc4]


if __name__ == '__main__':
    run_list = make_run_list(HU4)
    log_file = r"D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\watersheds_log.csv"
    for huc4 in run_list:
        p = Paths(huc4)
        try:
            last_tool = 'network'
            tool_count = run(p.huc4, last_tool)
            if tool_count > 0:
                p.log(log_file, '{}: SUCCESS'.format(last_tool))
        except Exception as e:
            p.log(log_file, repr(e))
            print(e)
        finally:
            arcpy.Delete_management('in_memory')

# TODO: Update mosaic feature
def update_mosaic(mosaic):
    mosaic_short = path.basename(mosaic)
    arcpy.AddRastersToMosaicDataset_management(mosaic, 'Raster Dataset', r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\QAQC\Watersheds\Watersheds_COPY',
                                               filter='*{}*jpg'.format(mosaic_short),
                                               update_overviews='UPDATE_OVERVIEWS',
                                               sub_folder='SUBFOLDERS',
                                               duplicate_items_action='EXCLUDE_DUPLICATES')

def dropbox_snapshot():
    pass


def completed_list(search_string):
    results = []
    for dirnames, dirpaths, filenames in arcpy.da.Walk(OUTPUTS_PARENT_DIR):
        for f in filenames:
            if search_string in f:
                results.append(f)
    return results

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
        nhd_network = nt.NHDNetwork(p.gdb)
        on_network = set(nhd_network.trace_up_from_hu4_outlets())
        with arcpy.da.UpdateCursor(cat, ['Permanent_Identifier', 'On_Main_Network']) as u_cursor:
            for row in u_cursor:
                permid, onmain = row
                onmain = 'Y' if permid in on_network else 'N'
                u_cursor.updateRow((permid, onmain))



def run_alternate(huc4, last_tool='network', wait=False, out_dir = '', burn_override=True):
    arcpy.env.overwriteOutput = True
    import Ned2Subregion as mosaic
    from burn_streams import burn_streams
    from WallsHU8 import wall as add_walls
    from GenerateSeeds import select_pour_points as make_catseed

    NED_DIR = r'D:\Continental_Limnology\Data_Downloaded\3DEP_National_Elevation_Dataset\Zipped'
    NED_FOOTPRINT = r'D:\Continental_Limnology\Data_Downloaded\3DEP_National_Elevation_Dataset\Unzipped Original\ned_13arcsec_g.shp'

    paths = Paths(huc4, hr=False)
    if out_dir:
        paths.out_dir = out_dir
        paths.locate_outputs()
    arcpy.AddMessage("Starting subregion {}...".format(paths.huc4))
    if last_tool:
        stop_index = ALT_TOOL_ORDER.index(last_tool)

    if not path.exists(paths.out_dir):
        os.mkdir(paths.out_dir)
    if not path.exists(paths.out_gdb):
        arcpy.CreateFileGDB_management(path.dirname(paths.out_gdb), path.basename(paths.out_gdb))

    start_time = dt.now()
    tool_count = 0
    # If the tool output doesn't exist yet, and the job control agrees it should be run, try running.
    # If the tool fails, continue after logging the error to the CSV.

    # Mosaic DEMS to subregion
    if not arcpy.Exists(paths.dem) and stop_index >= 0:
        arcpy.AddMessage('Mosaicking DEMs started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        work_dir = mosaic.stage_files(paths.gdb, NED_DIR, NED_FOOTPRINT, paths.out_dir, is_zipped=True)
        ned = mosaic.mosaic(work_dir, paths.gdb, paths.out_dir, available_ram=48) # path on disk = self.dem = 'NED13_####.tif'
        tool_count += 1
    #TODO: Remove any originals, NED but maybe also NHD, did we modify that at all?

    # Create hydrodem burn
    if not arcpy.Exists(paths.lagos_burn) and stop_index >= 1 and not burn_override:
        arcpy.AddMessage('Burning DEM started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        burn_temp = burn_streams(paths.dem, paths.gdb, paths.lagos_burn) #TODO: Modify tool to protect lakes from fill
        tool_count += 1

    # Fill and wall hydrodem
    if not arcpy.Exists(paths.lagos_fel) and stop_index >= 2:
        arcpy.AddMessage('Filling DEM started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        pitremove_cmd = 'mpiexec -n 8 pitremove -z {} -fel {}'.format(paths.lagos_burn, paths.lagos_fel)
        print(pitremove_cmd)
        sp.call(pitremove_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
        tool_count += 1

    # Create catseed
    if not arcpy.Exists(paths.lagos_gridcode) and stop_index >=3:
        nt.make_gridcode(paths.gdb, paths.lagos_gridcode)

    paths.lagos_catseed = path.join(paths.out_dir, 'pourpoints{}'.format(huc4), 'lagos_catseed.tif')
    if not arcpy.Exists(paths.lagos_catseed) and stop_index >= 3:
        arcpy.AddMessage('Identifying pour points started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        make_catseed(paths.gdb, paths.lagos_fel, paths.out_dir, paths.lagos_gridcode, LAGOS_LAKES)
        tool_count += 1

    # Create fdr
    if not arcpy.Exists(paths.lagos_fdr) and stop_index >= 4:
        arcpy.CheckOutExtension('Spatial')
        arcpy.AddMessage('Flow direction started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
        flow_dir = arcpy.sa.FlowDirection(paths.lagos_fel)
        # enforce same bounds as NHD fdr, so catchments have same HU4 boundary
        wbdhu4 = path.join(paths.gdb, 'WBDHU4')
        hu4 = arcpy.Select_analysis(wbdhu4, 'in_memory/hu4', "HUC4 = '{}'".format(huc4))
        hu4_buff = arcpy.Buffer_analysis(hu4, 'in_memory/hu4_buff', '10 meters')
        arcpy.env.snapRaster = flow_dir
        arcpy.Clip_management(flow_dir, '', paths.lagos_fdr, hu4_buff, clipping_geometry='ClippingGeometry')
        arcpy.CheckInExtension('Spatial')
        arcpy.Delete_management('in_memory/hu4')
        tool_count += 1


    # delineate catchments
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
        nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.iws_sheds, 'interlake')
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
        nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.network_sheds, 'network')
        tool_count += 1
    return tool_count

def make_alt_run_list(master_HU4):
    """Make a run list that will output one huc4 from most regions first, for QA purposes."""
    regions = ['{:02d}'.format(i) for i in range(1,19)]
    subregions = ['{:02d}'.format(i) for i in range(1,31)]
    template = []

    # do first 2 from each region first
    for s in subregions[:2]:
        template.extend(['{}{}'.format(r, s) for r in regions])
    # then go by region after that
    for r in regions:
        template.extend(['{}{}'.format(r, s) for s in subregions[2:]])

    huc4 = [r[0] for r in arcpy.da.SearchCursor(master_HU4, 'hu4_huc4')]

    # Select only the ones that don't have HR Plus data
    no_plus = [i for i in template if i in huc4 and i[:2] in ['04', '08', '18']]
    no_plus.remove('1806')
    no_plus.remove('1807')
    no_plus.remove('1808')
    no_plus.remove('1809')
    no_plus.remove('1810')
    no_plus.remove('1801')

    # Add regions that need alt-processing along with regular
    no_plus.extend(['0512', '0712', '1111', '0508'])
    no_plus.sort()

    return no_plus

def run_alt_batch():
    run_list = make_alt_run_list(HU4)
    log_file = r"D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\watersheds_log.csv"
    for huc4 in run_list:
        p = Paths(huc4)
        try:
            last_tool = 'network'
            if huc4 in ['0512', '0712', '1111', '0508']:
                tool_count = run_alternate(p.huc4, last_tool, out_dir = p.out_dir + '_alt')
            else:
                tool_count = run_alternate(p.huc4, last_tool)
            if tool_count > 0:
                p.log(log_file, '{}: SUCCESS'.format(last_tool))
        except Exception as e:
            p.log(log_file, repr(e))
            print(e)
        finally:
            arcpy.Delete_management('in_memory')

def add_ws_flags():
    # run_list = make_run_list(HU4)
    run_list  = make_run_list(HU4)
    failures = []
    for huc4 in run_list:
        print(huc4)
        p = Paths(huc4)
        nt.watershed_equality(p.iws_sheds, p.network_sheds)
        nt.qa_shape_metrics(p.iws_sheds, p.network_sheds, LAGOS_LAKES)


def add_hr_indicator():
    not_hr = ['0401', '0402', '0403', '0404', '0405', '0406', '0407',
              '0408', '0409', '0410', '0411', '0412', '0413', '0414',
              '0415', '0801', '0802', '0803',
              '0804', '0805', '0806', '0807', '0808', '0809',
              '1802', '1803', '1804', '1805']
    both = ['0512', '0712', '1111', '0508']
    hr = [h for h in make_run_list(HU4) if h not in not_hr and h not in both] + both
    p1 = [Paths(h) for h in not_hr]
    p2 = [Paths(h) for h in both]
    for p in p2:
        p.out_dir = p.out_dir + '_alt'
        p.locate_outputs()
    non_hr_paths = p1 + p2
    hr_paths = [Paths(h) for h in hr]

    for p in non_hr_paths:
        print(p.huc4)
        fcs = [p.local_catchments, p.iws_sheds, p.network_sheds]
        for fc in fcs:
            if not arcpy.ListFields(fc, 'VPUID'):
                arcpy.AddField_management(fc, 'watershedprocess', 'TEXT', field_length=20)
                if fc != p.local_catchments:
                    arcpy.AddField_management(fc, 'VPUID', 'TEXT', field_length=4)
                with arcpy.da.UpdateCursor(fc, ['VPUID', 'watershedprocess']) as cursor:
                    for row in cursor:
                        cursor.updateRow((p.huc4, 'NHD HR 2017'))

    for p in hr_paths:
        print(p.huc4)
        fcs = [p.local_catchments, p.iws_sheds, p.network_sheds]
        for fc in fcs:
            if not arcpy.ListFields(fc, 'VPUID'):
                arcpy.AddField_management(fc, 'watershedprocess', 'TEXT', field_length=20)
                if fc != p.local_catchments:
                    arcpy.AddField_management(fc, 'VPUID', 'TEXT', field_length=4)
                with arcpy.da.UpdateCursor(fc, ['VPUID', 'watershedprocess']) as cursor:
                    for row in cursor:
                        cursor.updateRow((p.huc4, 'NHDPlus HR Beta 2019'))


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


