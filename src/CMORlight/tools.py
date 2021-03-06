"""

Contains all the functions for processing the files

"""
import os
import sys

# netcdf4 Library
from netCDF4 import Dataset
from netCDF4 import num2date
from netCDF4 import date2num
import tempfile

# sub process library
import subprocess

# configuration
import get_configuration as config

# global variables
import settings

from datetime import datetime

# uuid support
import uuid

import traceback
import time as timepkg

# support logging
import logging
log = logging.getLogger("cmorlight")



# -----------------------------------------------------------------------------
def shell(cmd,logger=log):
    '''
    Call a shell command

    Parameters
    ----------

    cmd : str
        Shell command to execute
    logger : logging.Logger
        Which logger to use
    '''
    prc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    prc.wait()
    if prc.returncode != 0:
        raise Exception('Shell Error: %s for command: %s' % (prc.communicate()[0], cmd) )
    else:
        logger.debug(cmd)

    return prc.communicate()[0]


# -----------------------------------------------------------------------------
def get_input_path(derotated=False):
    ''' Read input path from settings, take derotated one if needed'''
    if derotated:
        retVal = settings.DirDerotated
    else:

        retVal = settings.DirIn
    return retVal

# -----------------------------------------------------------------------------
def get_var_lists():
    '''
    Extract all required variables from parameter table
    '''
    lst = []
    for row in sorted(settings.param):
        var=settings.param[row][config.get_config_value('index','INDEX_VAR')]
        if not var in lst: #to not append variables twice as they appear twice in params
            lst.append(var)
    return sorted(lst)


# -----------------------------------------------------------------------------
def set_attributes(params):
    '''
    fill dictionaries in settings with global attributes and additional netcdf attributes
    '''
    # get global attributes from file
    for name in settings.global_attr_list :
        try:
            settings.Global_attributes[name.strip()] = config.get_sim_value(name.strip())
        except:
            raise("Global attribute %s is in global_attr_list but is not defined in the configuration file!")

    #Invariant attributes
    settings.Global_attributes['project_id']="CORDEX"
    settings.Global_attributes['product']="output"

    # set addtitional netcdf attributes
    settings.netCDF_attributes['RCM_NAME'] = params[0]
    settings.netCDF_attributes['RCM_NAME_ORG'] = params[1]
    settings.netCDF_attributes['cf_name'] = params[config.get_config_value('index','INDEX_VAR')]
    settings.netCDF_attributes['long_name'] = params[config.get_config_value('index','INDEX_VAR_LONG_NAME')]
    settings.netCDF_attributes['standard_name'] = params[config.get_config_value('index','INDEX_VAR_STD_NAME')]
    settings.netCDF_attributes['units'] = params[config.get_config_value('index','INDEX_UNIT')]
    settings.netCDF_attributes['missing_value'] = config.get_config_value('float','missing_value')
    settings.netCDF_attributes['_FillValue'] = config.get_config_value('float','missing_value')


# -----------------------------------------------------------------------------
def create_outpath(res,var):
    '''
    Create and return the output path string from global attributes and dependent on resolution res and variable var
    '''
    result = ""

    if res == 'fx':
        result = "%s/%s/%s/%s/%s/%s/%s/%s/%s/%s/%s" % \
                    (settings.Global_attributes["project_id"],
                     settings.Global_attributes["product"],
                     settings.Global_attributes["CORDEX_domain"],
                     settings.Global_attributes["institute_id"],
                     settings.Global_attributes["driving_model_id"],
                     settings.Global_attributes["experiment_id"],
                     settings.Global_attributes["driving_model_ensemble_member"],
                     settings.Global_attributes["model_id"],
                     settings.Global_attributes["rcm_version_id"],
                     res,
                     var
                    )
    else:
        result = "%s/%s/%s/%s/%s/%s/%s/%s/%s/%s/%s" % \
                    (settings.Global_attributes["project_id"],
                     settings.Global_attributes["product"],
                     settings.Global_attributes["CORDEX_domain"],
                     settings.Global_attributes["institute_id"],
                     settings.Global_attributes["driving_model_id"],
                     settings.Global_attributes["experiment_id"],
                     settings.Global_attributes["driving_model_ensemble_member"],
                     settings.Global_attributes["model_id"],
                     settings.Global_attributes["rcm_version_id"],
                     res,
                     var
                    )
    if settings.use_version!="":
        result += "/" + settings.use_version
    return result


# -----------------------------------------------------------------------------
def create_filename(var,res,dt_start,dt_stop,logger=log):
    '''
    Create and return the filename string from global attributes and dependent on resolution res, variable var and time range dt_start to dt_stop
    '''

    #File naming different for instantaneous and interval representing (average,min,max) variables
    agg=settings.param[var][config.get_config_value('index','INDEX_FRE_AGG')] #subdaily aggregation method: average or instantaneous

    if res in ["1hr","3hr","6hr"]:
        if agg=="i":
            bounds=[["0000","2300"],["0000","2100"],["0000","1800"]]
        elif agg=="a":
            bounds=[["0030","2330"],["0130","2230"],["0300","2100"]]
        else:
            #TODO: do check of parameter table before to rule out this case
            bounds=[["0000","2100"],["0000","1800"]]
            logger.error("Subdaily aggregation method in column %s of parameter table must be 'i' or 'a'! Assumed instantaneous..." % config.get_config_value('index','INDEX_FRE_AGG'))

    if res == "1hr":
        dt_start = "%s%s" % (dt_start,bounds[0][0])
        dt_stop = "%s%s" % (dt_stop,bounds[0][1])
    if res == "3hr":
        dt_start = "%s%s" % (dt_start,bounds[1][0])
        dt_stop = "%s%s" % (dt_stop,bounds[1][1])
    elif res == "6hr":
        dt_start = "%s%s" % (dt_start,bounds[2][0])
        dt_stop = "%s%s" % (dt_stop,bounds[2][1])
    elif res == "day":
        dt_start = dt_start[:8]
        dt_stop = dt_stop[:8]
    elif res in ["mon","sem"]:
        dt_start = dt_start[:6]
        dt_stop = dt_stop[:6]
    elif res == 'fx':
        result = "%s_%s_%s_%s_%s_%s_%s_%s.nc" % (var,
                        settings.Global_attributes["CORDEX_domain"],
                        settings.Global_attributes["driving_model_id"],
                        settings.Global_attributes["experiment_id"],
                        settings.Global_attributes["driving_model_ensemble_member"],
                        settings.Global_attributes["model_id"],
                        settings.Global_attributes["rcm_version_id"],
                        res
                    )
        return result

    logger.debug("Filename start/stop: %s, %s" % (dt_start,dt_stop))

    result = ""
    result = "%s_%s_%s_%s_%s_%s_%s_%s_%s-%s.nc" % (var,
                    settings.Global_attributes["CORDEX_domain"],
                    settings.Global_attributes["driving_model_id"],
                    settings.Global_attributes["experiment_id"],
                    settings.Global_attributes["driving_model_ensemble_member"],
                    settings.Global_attributes["model_id"],
                    settings.Global_attributes["rcm_version_id"],
                    res,
                    dt_start,
                    dt_stop
                )
    return result


# -----------------------------------------------------------------------------
def compress_output(outpath,year=0,logger=log):
    ''' Compress files with nccopy'''

    if os.path.exists(outpath):
        try:
            ftmp_name = "%s/%s-%s.nc" % (settings.DirWork,year,str(uuid.uuid1()))
            cmd = "nccopy -k 4 -d 4 %s %s" % (outpath,ftmp_name)
            retval=shell(cmd,logger=logger)
            # remove help file
            os.remove(outpath)
            retval=shell("mv %s %s" % (ftmp_name,outpath),logger=logger)
        except:
            logger.error("Error while compressing ouput file: (%s)" % outpath)
    else:
        logger.error("File does not exist: (%s)" % outpath)


# -----------------------------------------------------------------------------
def set_attributes_create(outpath,res=None,year=0,logger=log):
    ''' Set and delete some (global) attributes'''

    if os.path.exists(outpath):
        f_out = Dataset(outpath,'r+')
        # set resolution if passed
        if res:
            f_out.setncattr("frequency",res)

        try: #delete unnecessary attribute
            f_out.variables["lon"].delncattr("_CoordinateAxisType")
            f_out.variables["lat"].delncattr("_CoordinateAxisType")
        except:
            pass

        # set new tracking_id
        f_out.setncattr("tracking_id",str(year)+str(uuid.uuid1()))
        # set new creation_date
        f_out.setncattr("creation_date",datetime.now().strftime(settings.FMT))

        if 'history' in f_out.ncattrs():
            f_out.delncattr("history")

        # commit changes
        f_out.sync()
        # close output file
        f_out.close()
    else:
        logger.error("File does not exist: (%s)" % outpath)


# -----------------------------------------------------------------------------
def set_coord_attributes(f_var,f_out):
    """
    Set the attributes of the pressure or height variable and the coordinates attribute of the variable f_var

    Parameters
    ----------

    f_var : netCDF4._netCDF4.Variable
        Variable of netCDF Dataset being processed
    f_out : netCDF4._netCDF4.Dataset
        Input file opened as a netCDF Dataset
    """

    if not f_out:
        log.warning("No output object for setting coordinates value available!")
        return

    if 'plev' in f_out.variables:
        var_out = f_out.variables ['plev']
        var_out.units = "Pa"
        var_out.axis = "Z"
        var_out.positive = "down"
        var_out.long_name = "pressure"
        var_out.standard_name = "air_pressure"
        if 'lon' in f_out.variables and 'lat' in f_out.variables:
            f_var.coordinates = 'plev lat lon'
        else:
            cmd = "No lon/lat coordinates available!"
            raise Exception(cmd)
        #elif 'rlon' in f_out.variables and 'rlat' in f_out.variables:
            #f_var.coordinates = 'plev rlat rlon'
        #else:
            #f_var.coordinates = 'plev'

    elif 'height' in f_out.variables:
        var_out = f_out.variables ['height']
        var_out.units = "m"
        var_out.axis = "Z"
        var_out.positive = "up"
        var_out.long_name = "height"
        var_out.standard_name = "height"
        if 'lon' in f_out.variables and 'lat' in f_out.variables:
            f_var.coordinates = 'height lat lon'
        else:
            cmd = "No lon/lat coordinates available!"
            raise Exception(cmd)
        #elif 'rlon' in f_out.variables and 'rlat' in f_out.variables:
            #f_var.coordinates = 'height rlat rlon'
        #else:
            #f_var.coordinates = 'height'
    else:
        if 'lon' in f_out.variables and 'lat' in f_out.variables:
            f_var.coordinates = 'lat lon'
        else:
            cmd = "No lon/lat coordinates available!"
            log.error(cmd)
            raise Exception(cmd)
        #elif 'rlon' in f_out.variables and 'rlat' in f_out.variables:
            #f_var.coordinates = 'rlat rlon'


# -----------------------------------------------------------------------------
def new_dataset_version():
    '''
    Create and return new dataset version from current date
    this will be inserted in the output directory structure
    if add_version_to_outpath=True in configuration file
    '''
    return datetime.now().strftime("%Y%m%d")


# -----------------------------------------------------------------------------
def get_out_dir(var,res):
    '''
    Create and return the complete output path string using the resolution res and the variable var
    and make the corresponding directory

    '''
    outpath = create_outpath(res,var)
    outpath = "%s/%s" % (settings.DirOut,outpath)
    try:
        os.makedirs(outpath)
    except:
        pass
    return outpath

# -----------------------------------------------------------------------------
def proc_chunking(params,reslist):
    """
    create AGG_DAY (daily), AGG_MON (monthly) and/or AGG_SEM (seasonal) years chunks of yearly input files
    (as defined in configuration file; default: 5,10 and 10, respectively) depending on resolutions in reslist
    """

    # get cdf variable name
    var = params[config.get_config_value('index','INDEX_VAR')]

    for res in reslist:
        if res == 'day':
            max_agg = config.get_config_value('index','AGG_DAY')
        elif res == 'mon':
            max_agg = config.get_config_value('index','AGG_MON')
        elif res == 'sem':
            max_agg = config.get_config_value('index','AGG_SEM')
        else:
            cmd = "Resolution (%s) is not supported in chunking, keep it as it is." % res
            log.debug(cmd)
            continue
        log.log(35,"resolution: %s " % (res))
        indir = get_out_dir(var,res)
        outdir = indir
        #extra directory to put chunked files into
        if config.get_config_value('settings','chunk_into',exitprog=False)!="":
            outdir=outdir+"/"+config.get_config_value('settings','chunk_into',exitprog=False)

        log.info("Output directory: %s" % outdir)
        for dirpath,dirnames,filenames in os.walk(indir):
            f_list = []
            start_date = 0
            for f in sorted(filenames):
                if f[-3:] != ".nc": #skip unsuitable files
                    continue
                idx = f.index("%s_" % res)
                if start_date == 0:
                    if res == 'day':
                        start_date = int(f[idx+len("%s_" % res):f.index(".nc")][:8])
                    elif res == 'mon' or res == 'sem':
                        start_date = int(f[idx+len("%s_" % res):f.index(".nc")][:6])

                start_yr=int(f[idx+len("%s_" % res):f.index(".nc")][:4])
                idx = f.rindex("-")
                if res == 'day':
                    stop_date = int(f[idx+1:f.index(".nc")][:8])
                elif res == 'mon' or res == 'sem':
                    stop_date = int(f[idx+1:f.index(".nc")][:6])

                # if there is more than one year between start and stop year: skip file
                stop_yr = int(f[idx+1:f.index(".nc")][:4])
                if stop_yr > start_yr + 1:
                    log.debug("%s is not a yearly file. Skipping..." % f)
                    continue

                f_list.append("%s/%s" % (indir,f))
                if stop_yr % max_agg == 0:

                    do_chunking(f_list,var,res,start_date, stop_date,outdir)
                    # reset parameter
                    f_list = []
                    start_date = 0
            # do the same for whats left in list
            if len(f_list) > 1:
                do_chunking(f_list,var,res,start_date, stop_date,outdir)

# -----------------------------------------------------------------------------
def do_chunking(f_list,var,res,start_date, stop_date, outdir):
    """  Execute actual chunking of files in f_list """

    flist=""
    if len(f_list) > 1:

        # generate complete output path with output filename
        outfile = create_filename(var,res,str(start_date),str(stop_date))
        # generate outpath with outfile and outdir

        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        outpath = "%s/%s" % (outdir,outfile)

        # generate input filelist
        for y in f_list:
            flist = ("%s %s " % (flist,y))
        # cat files to aggregation file
        # skip if exist
        if (not os.path.isfile(outpath)) or config.get_config_value('boolean','overwrite'):
            if os.path.isfile(outpath):
                log.info("Output file exists: %s, overwriting..." % (outfile))
            else:
                log.info("Concatenating files to %s" % (outfile))
            retval=shell("ncrcat -h -O %s %s " % (flist,outpath))

            # set attributes
            set_attributes_create(outpath,res)
        else:
            log.info("Output file exist: %s, skipping!" % (outfile))
                                    # remove source files
        if config.get_config_value('boolean','remove_src'):
            retval=shell("rm -f %s " % (flist))

# -----------------------------------------------------------------------------
def leap_year(year, calendar='standard'):
    """    Determine if year is a leap year    """
    leap = False
    if ((calendar in ['standard','gregorian','proleptic_gregorian','julian']) and (year % 4 == 0)):
        leap = True
        if ((calendar == 'proleptic_gregorian') and (year % 100 == 0) and (year % 400 != 0)):
            leap = False
        elif ((calendar in ['standard', 'gregorian']) and (year % 100 == 0) and (year % 400 != 0) and (year < 1583)):
            leap = False
    return leap


# -----------------------------------------------------------------------------
def add_vertices(f_out,logger=log):
    """    add vertices to output file from vertices file    """
    # read vertices from file if exist
    if os.path.isfile(config.get_sim_value("vertices_file")):
        f_vert = Dataset(config.get_sim_value("vertices_file"),'r')
        if 'vertices' in f_vert.dimensions.keys() and 'vertices' not in f_out.dimensions.keys():
            # is present I know the content of this file
            if 'vertices' in f_vert.dimensions.keys():
                f_out.createDimension('vertices',len(f_vert.dimensions['vertices']))
            else:
                # standard len
                f_out.createDimension('vertices',4)
        if 'lon_vertices' in f_vert.variables.keys() and 'lon_vertices' not in f_out.variables.keys():
            lon_vertices = f_vert.variables['lon_vertices']
            # create lon_vertices in output
            var_out = f_out.createVariable('lon_vertices',datatype='f',dimensions=lon_vertices.dimensions)
            # copy content to new datatype
            if 'lon' in f_vert.variables.keys():
                f_lon = f_vert.variables['lon']
                if 'units' in f_lon.ncattrs():
                    var_out.units = str(f_lon.units)
                else:
                    var_out.units = "degrees_east"
                if not 'lon' in f_out.variables.keys():
                    copy_var(f_vert,f_out,'lon',logger=logger)
            else:
                var_out.units = "degrees_east"
            f_out_lon = f_out.variables['lon']
            f_out_lon.bounds = 'lon_vertices'
            var_out[:] = lon_vertices[:]
            logger.info("Vertices (lon) set!")
        if 'lat_vertices' in f_vert.variables.keys() and 'lat_vertices' not in f_out.variables.keys():
            lat_vertices = f_vert.variables['lat_vertices']
            # create lat_vertices in output
            #var_out = f_out.createVariable('lat_vertices',datatype='f',dimensions=['rlat','rlon','vertices'])
            var_out = f_out.createVariable('lat_vertices',datatype='f',dimensions=lat_vertices.dimensions)
            # copy content to new datatype
            if 'lat' in f_vert.variables.keys():
                f_lat = f_vert.variables['lat']
                if 'units' in f_lon.ncattrs():
                    var_out.units = str(f_lat.units)
                else:
                    var_out.units = "degrees_north"
                if not 'lat' in f_out.variables.keys():
                    copy_var(f_vert,f_out,'lat',logger=logger)
            else:
                var_out.units = "degrees_north"
            f_out_lat = f_out.variables['lat']
            f_out_lat.bounds = 'lat_vertices'
            var_out[:] = lat_vertices[:]
            logger.info("Vertices (lat) set!")

        # commit changes
        f_out.sync()

    else:
        logger.error("Vertices file %s does not exist! No vertices added..." % config.get_sim_value("vertices_file") )
# -----------------------------------------------------------------------------
def check_resolution(params,res,process_table_only):
    '''
    check whether resolution "res" is declared in specific row of variables table "param".
    '''
    if res in ["1hr","3hr","6hr","12hr"]:
        res_hr=(float(res[:-2])) #extract time resolution in hours
        freq_table=params[config.get_config_value('index','INDEX_FRE_SUB')]
        freq=24./res_hr
    elif res=="day":
        freq_table=params[config.get_config_value('index','INDEX_FRE_DAY')]
        freq=1. #requested samples per day
    elif res=="mon":
        freq_table=params[config.get_config_value('index','INDEX_FRE_MON')]
        freq=1. #requested samples per month
    elif res=="sem":
        freq_table=params[config.get_config_value('index','INDEX_FRE_SEM')]
        freq=1. #requested samples per month
    elif res == 'fx':
        freq_table=params[config.get_config_value('index','INDEX_FX')]
        freq=freq_table
    else:
        log.warning("Time resolution (%s) is not supported, skipping..." % res)
        return False

    #if process_table_only is set: check if requested time resolution is declared in table
    if (freq_table=="" or float(freq_table) != freq) and process_table_only:
        log.info("Requested time resolution (%s) not declared in parameter table. Skipping.." % res)
        return False
    else:
        return True


# -----------------------------------------------------------------------------

def get_attr_list(var_name):
    '''
    set pre defined attributes for variables lon,lat
    '''
    att_lst = {}
    if var_name == 'lon':
        att_lst['standard_name'] = 'longitude'
        att_lst['long_name'] = 'longitude'
        att_lst['units'] = 'degrees_east'
        if config.get_config_value('boolean','add_vertices') == True:
            att_lst['bounds'] = "lon_vertices"
    elif var_name == 'lat':
        att_lst['standard_name'] = 'latitude'
        att_lst['long_name'] = 'latitude'
        att_lst['units'] = 'degrees_north'
        if config.get_config_value('boolean','add_vertices') == True:
            att_lst['bounds'] = "lat_vertices"
    return att_lst


# -----------------------------------------------------------------------------
def copy_var(f_in,f_out,var_name,logger=log):
    '''
    copy variable with corresponding attributes from in_file to out_file if present there
    '''
    if var_name in f_in.variables and var_name not in f_out.variables:
        var_in = f_in.variables[var_name]
        if var_name in ['lat','lon','rotated_latitude_longitude','rotated_pole']:
            new_datatype = 'd'
        else:
            new_datatype = var_in.datatype
        var_out = f_out.createVariable(var_name,datatype=new_datatype,dimensions=var_in.dimensions )
        # set all as character converted with str() function
        if var_name in ['lat','lon']:
            att_lst = get_attr_list(var_name)
        else:
            att_lst = {}
            for k in var_in.ncattrs():
                if config.get_config_value('boolean','add_vertices') == False and k == 'bounds':
                    continue
                att_lst[k] = var_in.getncattr(k)

        var_out.setncatts(att_lst)
        # copy content to new datatype
        if var_name not in ['rotated_latitude_longitude','rotated_pole']:
            var_out[:] = var_in[:]
        logger.info("Variable %s added" % var_name)


# -----------------------------------------------------------------------------
def add_coordinates(f_out,logger=log):
    """
    add lat,lon and rotated_pole to output file from coordinates file if present there
    """
    if os.path.isfile(settings.coordinates_file):
        f_coor = Dataset(settings.coordinates_file,'r')
        try:
            # copy lon
            copy_var(f_coor,f_out,'lon',logger=logger)
            # copy lat
            copy_var(f_coor,f_out,'lat',logger=logger)
            #copy rotated pole
            copy_var(f_coor,f_out,'rotated_pole',logger=logger)
            copy_var(f_coor,f_out,'rotated_latitude_longitude',logger=logger)

            # commit changes
            f_out.sync()
            f_coor.close()
        except IndexError as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value,exc_traceback,limit=10)
            sys.exit("\n Coordinates file does not have the same resolution as the input data! Change it!")
    else:
        raise Exception("Coordinates file %s does not exist!" % settings.coordinates_file)
# -----------------------------------------------------------------------------
def get_derotate_vars():
    '''
    Read from variables table all variables that are supposed to be derotated
    '''
    lst = []
    for row in settings.param:
        rotate=settings.param[row][config.get_config_value('index','INDEX_VAR_ROTATE')]
        if rotate.lower() in ['derotate','yes','1']:
            var=settings.param[row][config.get_config_value('index','INDEX_VAR')]
            if not var in lst:
                lst.append(var)
    return lst


# -----------------------------------------------------------------------------
def process_file_fix(params,in_file):
    '''
    Main function for constant variables: process input_file
    '''
    # get cdf variable name

    var = params[config.get_config_value('index','INDEX_VAR')]
    # fixed
    res = 'fx'

    # create object from netcdf file to access all parameters and attributes
    f_in = Dataset(in_file,"r")

    for name in f_in.ncattrs():
        if name in settings.global_attr_file: #only take attribute from file if in this list
            settings.Global_attributes[name] = str(f_in.getncattr(name))

    #TODO: ist this fix?
    name = "driving_model_ensemble_member"
    settings.Global_attributes[name] = 'r0i0p0'

    # out directory
    outdir = get_out_dir(var,'fx')
    # get file name
    outfile = create_filename(var,'fx','','')
    # create complete outpath: outdir + outfile
    outpath = "%s/%s" % (outdir,outfile)
    # skip file if exists or overwrite
    if os.path.isfile(outpath):
        log.info("Output file exists: %s" % (outpath))
        if not config.get_config_value('boolean','overwrite'):
            log.info("Skipping...")
            return
        else:
            log.info("Overwriting..")
    log.info("Output to: %s" % (outpath))

    # create object for output file
    global f_out

    f_out = Dataset(outpath,'w')

    # create dimensions in target file
    for name, dimension in f_in.dimensions.items():
        # skip dimension
        if name in settings.varlist_reject or name in ['bnds','time']:
            continue
            #f_out.createDimension(name, len(dimension) if not dimension.isunlimited() else None)
        else:
            if dimension not in ['bnds','time']:
                f_out.createDimension(name, len(dimension) if not dimension.isunlimited() else None)

    # set dimension vertices only if set to True in settings file
    if config.get_config_value('boolean','add_vertices') == True:
        f_out.createDimension('vertices',4)

    try:
        mulc_factor = float(params[config.get_config_value('index','INDEX_COVERT_FACTOR')].strip().replace(',','.'))
    except ValueError:
        log.warning("No conversion factor set for %s in parameter table. Setting it to 1..." % params[config.get_config_value('index','INDEX_RCM_NAME')])
        mulc_factor = 1.0
    if mulc_factor == 0:
        log.warning("Conversion factor for %s is set to 0 in parameter table. Setting it to 1..." % params[config.get_config_value('index','INDEX_RCM_NAME')])
        mulc_factor = 1.0

    if config.get_config_value('boolean','nc_compress') == True:
        log.info("COMPRESS all variables")
    else:
            log.info("NO COMPRESS")
    for var_name, variable in f_in.variables.items():
        # don't copy time_bnds if cm == point or variable time_bnds
        log.debug("VAR: %s" % (var_name))

        if var_name in ['time','time_bnds','bnds']:
            continue
        var_in = f_in.variables[var_name]
        # create output variable
        if var_name in ['rlon','rlat']:
            data_type = 'd'
        elif var_name in ['lon','lat']:#already added as variables further down
            data_type = 'd'
            continue
        elif var_name in settings.varlist_reject:
            continue
        else:
            data_type = var_in.datatype
        # at variable creation set fill_vlue, later is impossible
        # also set the compression

        # skip 'pressure'!!
        my_lst = []
        for dim in var_in.dimensions:
            log.debug("DIM: %s" % (dim))
            if dim in ['time','time_bnds','bnds']:
                continue
            if str(dim) not in settings.varlist_reject:
                my_lst.append(dim)
        var_dims = tuple(my_lst)
        log.debug("Attributes (of variable %s): %s" % (var_name,var_in.ncattrs()))


  #      if var_name not in f_out.variables:
        if var_name in [var,settings.netCDF_attributes['RCM_NAME_ORG']]:
            # TODO:test on FillValue for variables: mrfso,mrso,mrro
            # could be negativ!
            if config.get_config_value('boolean','nc_compress') == True:
                var_out = f_out.createVariable(var_name,datatype=data_type,
                    dimensions=var_dims,complevel=4,fill_value=settings.netCDF_attributes['missing_value'])
            else:
                var_out = f_out.createVariable(var_name,datatype=data_type,
                    dimensions=var_dims,fill_value=settings.netCDF_attributes['missing_value'])

        else:
            if config.get_config_value('boolean','nc_compress') == True:
                var_out = f_out.createVariable(var_name,datatype=data_type,dimensions=var_dims,complevel=4)
            else:
                var_out = f_out.createVariable(var_name,datatype=data_type,dimensions=var_dims)


        # set all as character converted with str() function

        if var_name in ['lat','lon']:
            att_lst = get_attr_list(var_name)
        else:
            att_lst = {}
            for k in var_in.ncattrs():
                if config.get_config_value('boolean','add_vertices') == False and k == 'bounds':
                    continue
                if k in ['coordinates']:
                    continue
               # if k != '_FillValue':
                att_lst[k] = var_in.getncattr(k)
                #if k in ['grid_north_pole_latitude','grid_north_pole_longitude']:
                 #   att_lst[k] = np.float32(var_in.getncattr(k))
            if var_name == 'rlon':
                att_lst['axis'] = 'X'
                att_lst['long_name'] = 'longitude in rotated pole grid'

            elif var_name == 'rlat':
                att_lst['axis'] = 'Y'
                att_lst['long_name'] = 'latitude in rotated pole grid'

        var_out.setncatts(att_lst)


        # copy content to new datatype
        log.debug("Copy from input: %s" % (var_out.name))

        if var_name in ['rlon','rlat','rotated_pole','rotated_latitude_longitude']:
            var_out[:] = var_in[:]
        else:
            var_out[:] = mulc_factor * var_in[:]



    # commit changes
    f_out.sync()

    ###################################
    # do some additional settings
    ###################################
    # rename variable
    try:
        f_out.renameVariable(settings.netCDF_attributes['RCM_NAME_ORG'],settings.netCDF_attributes['cf_name'])
    except:
        log.warning("Variable has cf name already: %s" % (var))

    # set all predefined global attributes
    f_out.setncatts(settings.Global_attributes)
    log.info("Global attributes set!")


    # add lon/lat variables
    add_coordinates(f_out)

    # commit changes
    f_out.sync()

    # exist in some output (e.g. CCLM) in CORDEX, default: False
    if config.get_config_value('boolean','add_vertices') == True:
        add_vertices(f_out)

    # create variable object to output file
    f_var = f_out.variables[settings.netCDF_attributes['cf_name']]
    # set additional variables attributes
    f_var.standard_name = settings.netCDF_attributes['standard_name']
    f_var.long_name = settings.netCDF_attributes['long_name']
    f_var.units = settings.netCDF_attributes['units']
    #add coordinates attribute to fx-variables
    f_var.coordinates = 'lon lat'



    # set attribute missing_value
    f_var.missing_value = settings.netCDF_attributes['missing_value']
    log.debug("#####################: %s" % (f_var.ncattrs()))
    try:
        f_var.setncattr('grid_mapping','rotated_pole')
    except:
        log.warning("Variable '%s' does not exist." % ("rotated_pole"))

    # commit changes
    f_out.sync()

    #close output file
    f_out.close()


    # set attributes: frequency,tracking_id,creation_date
    set_attributes_create(outpath,res)

    # ncopy file to correct output format
    if config.get_config_value('boolean','nc_compress') == True:
        compress_output(outpath)
    log.info("Variable attributes set!")

    # close input file
    f_in.close()


# -----------------------------------------------------------------------------
def proc_seasonal_mean(params,year):
    ''' create seasonal mean for one variable and one year from daily data '''

    if config.get_config_value("integer","multi") > 1:
        logger = logging.getLogger("cmorlight_"+year)
    else:
        logger = logging.getLogger("cmorlight")

    # get cdf variable name
    var = params[config.get_config_value('index','INDEX_VAR')]
    # first get daily data
    res = "day"
    cm_type = params[config.get_config_value('index','INDEX_VAR_CM_DAY')]
    # get output directory of daily data: input for seasonal
    indir = get_out_dir(var,res)
    logger.info("Inputdir: %s" % (indir))

    # seasonal mean
    res = 'sem'
    # get cell method
    cm_type = params[config.get_config_value('index','INDEX_VAR_CM_SEM')]

    #create possible filenames and check their existence -> skip or overwrite file
    outdir = get_out_dir(var,res)
    outfile1 = create_filename(var,res,year+"03",year+"11",logger=logger)
    outpath1 = "%s/%s" % (outdir,outfile1)
    outfile2 = create_filename(var,res,str(int(year)-1)+"12",year+"11",logger=logger)
    outpath2 = "%s/%s" % (outdir,outfile2)

    if os.path.isfile(outpath1) or os.path.isfile(outpath2):
        if os.path.isfile(outpath1):
            logger.info("Output file exists: %s" % (outpath1))
        else:
            logger.info("Output file exists: %s" % (outpath2))

        if not config.get_config_value('boolean','overwrite'):
            logger.info("Skipping...")
            return
        else:
            logger.info("Overwriting..")


    # get files with monthly data from the same input (if exist)
    input_exist=False  #is changed if input file was found
    for dirpath,dirnames,filenames in os.walk(indir):

        if cm_type != '':
            t_delim = 'mean over days'
            if t_delim in cm_type:
#                cm0 = cm_type[cm_type.index(' '):]
                cm = 'mean' #cm_type[cm_type.index(t_delim)+len(t_delim):]

            else:
                cm = cm_type
            logger.info("Cell method used for cdo command: %s" % (cm))

            outdir = get_out_dir(var,res)
            f_lst = sorted(filenames)
            i = 0
            for f in f_lst:
                year_act=f.split("_")[-1][:4]
                if year_act != year: #only process file if the year is correct
                    i=i+1

                    continue
                else:
                    input_exist=True

                # first a temp file
                ftmp_name = "%s/%s-%s%s" % (settings.DirWork,year,str(uuid.uuid1()),'-help.nc')
                # generate outpath with outfile and outdir
                f = "%s/%s" % (dirpath,f)

                # for season the last month from previous year is needed
                if i == 0:
                    cmd = "cdo -f %s -seas%s -selmonth,3/11 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,f,ftmp_name)
                    retval=shell(cmd,logger=logger)

                else:
                    # first: last December of previous year
                    f_hlp12 = tempfile.NamedTemporaryFile(dir=settings.DirWork,delete=False,suffix=str(year)+"sem")
                    f_prev = "%s/%s" % (dirpath,f_lst[i-1])
                    if config.get_config_value("integer","multi") > 1:
                        timepkg.sleep(3)#wait for previous year to definitely finish when multiprocessing
                    cmd = "cdo -f %s selmonth,12 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),f_prev,f_hlp12.name)
                    retval = shell(cmd,logger=logger)

                    # second: month 1...11 of actual year
                    f_hlp1_11 = tempfile.NamedTemporaryFile(dir=settings.DirWork,delete=False,suffix=str(year)+"sem")
                    cmd = "cdo -f %s selmonth,1/11 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),f,f_hlp1_11.name)
                    retval = shell(cmd,logger=logger)

                    # now concatenate all 12 month
                    f_hlp12_11 = tempfile.NamedTemporaryFile(dir=settings.DirWork,delete=False,suffix=str(year)+"sem")
                    cmd = "ncrcat -h -O %s %s %s" % (f_hlp12.name,f_hlp1_11.name,f_hlp12_11.name)
                    retval = shell(cmd,logger=logger)

#                    cmd = "cdo -f %s -s timsel%s,3,2 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,f_hlp2.name,ftmp_name)
#                    cmd = "cdo -f %s -s timsel%s,3 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,f_hlp12_11.name,ftmp_name)
#                    cmd = "cdo -f %s timsel%s,3 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,f_hlp12_11.name,ftmp_name)
                    cmd = "cdo -f %s seas%s,3 %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,f_hlp12_11.name,ftmp_name)
                    retval = shell(cmd,logger=logger)

                    # remove all temp files
                  #  os.remove(f_hlp12.name)
                   # os.remove(f_hlp1_11.name)
                    #os.remove(f_hlp12_11.name)

                # create netcdf4 object from file
                f_tmp = Dataset(ftmp_name,'r+')

                # commit changes
                f_tmp.sync()

                # now copy rotated pole variable to output
                f_in = Dataset(f,'r')

                # variable object
                f_var = f_tmp.variables[var]
                try:
                    #if not 'rotated_latitude_longitude' in f_tmp.variables.keys() and 'rotated_pole' in f_tmp.variables.keys():
                        #f_tmp.renameVariable('rotated_pole','rotated_latitude_longitude')
                    if not 'rotated_pole' in f_tmp.variables.keys():
                        var_name = 'rotated_pole'
                        if var_name in f_in.variables.keys():
                            copy_var(f_in,f_tmp,var_name,logger=logger)
                except:
                    logger.info("Variable '%s' does not exist." % ("rotated_pole"))

                # copy also height an plev: they are correct at that point
                for var_name in ['lat','lon','rotated_pole','plev','height']:
#                    print var_name,var_name in f_in.variables.keys(),var_name not in f_tmp.variables
                    if var_name in f_in.variables.keys() and var_name not in f_tmp.variables.keys():
                        copy_var(f_in,f_tmp,var_name,logger=logger)
                f_var.setncattr('grid_mapping','rotated_pole')
                f_var.cell_methods = "time: %s" % (cm_type)

                # commit changes
                f_tmp.sync()

                # close input object
                f_in.close()

                # set attribute coordinates
                set_coord_attributes(f_var=f_tmp.variables[var],f_out=f_tmp)
                #Delete unnecessary argument

                # commit changes
                f_tmp.sync()

                # get time variable from input
                time = f_tmp.variables['time']
                time_bnds = f_tmp.variables['time_bnds']
                # get the first time value and convert to date
                dt1 = num2date(time_bnds[0,0],time.units,time.calendar)
                # get the last time value and convert to date
                # attention: minus ONE DAY to meet the end month
                dt2 = num2date(time_bnds[len(time_bnds)-1,1]-1,time.units,time.calendar)
                dt_start = str(dt1)[:7].replace("-","")
                dt_stop = str(dt2)[:7].replace("-","")

                # close output object
                f_tmp.close()

                # create outpath to store
                outfile = create_filename(var,res,dt_start,dt_stop,logger=logger)
                outpath = "%s/%s" % (outdir,outfile)
                # rename temp file to output filename outpath
                retval = shell("mv %s %s" % (ftmp_name,outpath))

                # set attributes
                set_attributes_create(outpath,res,year)
                # correct netcdf version
                if config.get_config_value('boolean','nc_compress') == True:
                    compress_output(outpath,year,logger=logger)

                # exist in some output (e.g. CCLM) in CORDEX, default: False
                if config.get_config_value('boolean','add_vertices') == True:
                    f_out = Dataset(outpath,'r+')
                    add_vertices(f_out)
                    f_out.close()

                # next file index in the list
                i += 1
            if not input_exist:
                logger.warning("Input file (daily resolution) for seasonal processing does not exist. Skipping this year...")
            else:
                break
        else:
            logger.warning("No cell method set for this variable (%s) and time resolution (%s)." % (var,res))


# -----------------------------------------------------------------------------
def derotate_uv(params,in_file,var,logger=log):
    """
    derotate input file if this is declared for the variable in the variables table (generally for wind speed variables)
    """
    logger.info("Derotating file")
    #set environment variable correct

    if var not in get_derotate_vars():
        logger.warning("Variable not derotated as this was not declared in parameter table!")
        return

    #assign u and v variables
    filename = in_file.split("/")[-1]
    varRCM = params[config.get_config_value('index','INDEX_RCM_NAME')]
    if var.find("u") == 0:
        in_var_u = varRCM
        in_var_v =  varRCM.replace('U','V')
        filename_u = filename
        filename_v = filename.replace('U','V')

    elif var.find("v") == 0:
        in_var_v = varRCM
        in_var_u =  varRCM.replace('V','U')
        filename_v = filename
        filename_u = filename.replace('V','U')

    else:
        cmd="Error in parameter table. Variable to be derotated starts with neither 'u' nor 'v' !"
        logger.error(cmd)
        raise Exception(cmd)

    #filenames
    in_file_v = "%s/%s/%s" % (settings.DirIn,in_var_v,filename_v)
    in_file_u = "%s/%s/%s" % (settings.DirIn,in_var_u,filename_u)
    if not os.path.isfile(in_file_u) or not os.path.isfile(in_file_v):
        logger.warning("File %s or %s does not exist! Skipping this variable..." % (in_file_u,in_file_v))
        return
    out_dir_u = "%s/%s" % (get_input_path(True),in_var_u)
    out_dir_v = "%s/%s" % (get_input_path(True),in_var_v)
    out_file_u = "%s/%s" % (out_dir_u,filename_u)
    out_file_v = "%s/%s" % (out_dir_v,filename_v)

    # make directories
    try:
        os.makedirs(out_dir_u)
        os.makedirs(out_dir_v)
    except:
        pass

    start_range = in_file[in_file.rindex('_')+1:in_file.rindex('.')]

    # start if output files do NOT exist
    if (not os.path.isfile(out_file_u)) or (not os.path.isfile(out_file_v)) or (config.get_config_value('boolean','overwrite')):
        out_file = "%s/UV_%s-%s_%s.nc" % (settings.DirWork,in_var_u,in_var_v,start_range)
        out_file_derotate = "%s/UV_%s-%s_%s_derotate.nc" % (settings.DirWork,in_var_u,in_var_v,start_range)
        if not os.path.isfile(out_file) or config.get_config_value('boolean','overwrite'):
            cmd = "cdo -O merge %s %s %s" % (in_file_u,in_file_v,out_file)
            retval = shell(cmd,logger=logger)

        # only these two have the names as CCLM variable in the file
        try:
            if in_var_u == "U_10M" or in_var_v == "V_10M":
                if not os.path.isfile(out_file_derotate) or config.get_config_value('boolean','overwrite'):
                    cmd = "cdo -O rotuvb,%s,%s %s %s" % (in_var_u,in_var_v,out_file,out_file_derotate)
                    retval = shell(cmd,logger=logger)

                if not os.path.isfile(out_file_u) or config.get_config_value('boolean','overwrite'):
                    cmd = "cdo -O selvar,%s %s %s" % (in_var_u,out_file_derotate,out_file_u)
                    retval = shell(cmd,logger=logger)

                if not os.path.isfile(out_file_v) or config.get_config_value('boolean','overwrite'):
                    cmd = "cdo -O selvar,%s %s %s" % (in_var_v,out_file_derotate,out_file_v)
                    retval = shell(cmd,logger=logger)

            # all other have only U and V inside
            else:
                if not os.path.isfile(out_file_derotate) or config.get_config_value('boolean','overwrite'):
                    cmd = "cdo -O rotuvb,U,V %s %s" % (out_file,out_file_derotate)
                    retval = shell(cmd,logger=logger)
                if not os.path.isfile(out_file_u) or config.get_config_value('boolean','overwrite'):
                    cmd = "cdo -O selvar,U %s %s" % (out_file_derotate,out_file_u)
                    retval = shell(cmd,logger=logger)
                if not os.path.isfile(out_file_v) or config.get_config_value('boolean','overwrite'):
                    cmd = "cdo -O selvar,V %s %s" % (out_file_derotate,out_file_v)
                    retval = shell(cmd,logger=logger)

        except Exception as e:
            cmd=str(e)+"\n Derotation failed. Typing 'export IGNORE_ATT_COORDINATES=1' into your shell before starting the script might solve the problem."
            logger.error(cmd)
            raise Exception(cmd)

        #remove temp files
        if os.path.isfile(out_file):
            os.remove(out_file)
        if os.path.isfile(out_file_derotate):
            os.remove(out_file_derotate)

    return out_file_u, out_file_v
# -----------------------------------------------------------------------------
def process_file(params,in_file,var,reslist,year):
    '''
    Main function for time-dependent variables: process input_file at resolutions defined in reslist

    '''

    if config.get_config_value("integer","multi") > 1:
        logger = logging.getLogger("cmorlight_"+year)
    else:
        logger = logging.getLogger("cmorlight")

    #derotate if required
    if var in get_derotate_vars() and config.get_config_value('boolean','derotate_uv'):
        in_file_u, in_file_v = derotate_uv(params,in_file,var,logger)
        #change input file
        if var.find("u")!=-1:
            in_file=in_file_u
        else:
            in_file=in_file_v
        logger.info("Changed input file to derotated file: %s" % in_file)

    # create object from netcdf file to access all parameters and attributes

    f_in = Dataset(in_file,"r")

    for name in f_in.ncattrs():
        if name in settings.global_attr_file: #only take attribute from file if in this list
            settings.Global_attributes[name] = str(f_in.getncattr(name))

    # get time variable from input
    time_in = f_in.variables['time']

    # get time_bnds variable from input
    #if 'time_bnds' in f_in.variables.keys():
        #time_bnds_in = f_in.variables['time_bnds']

    if 'calendar' in time_in.ncattrs():
        in_calendar = str(time_in.calendar)
    else:
        in_calendar = config.get_sim_value("calendar",exitprog = False)
        if in_calendar=="":
            raise Exception("Calendar attribute not found input file! Specify calendar in simulation settings section of configuration file instead!")

   # in_calendar=config.get_sim_value("calendar")

    # mark for use another time unit
    if config.get_config_value('boolean','use_in_units'):
        time_in_units = config.get_config_value('settings','in_units')
    else:
        time_in_units = time_in.units

    # now get the 'new' time/date
    dt_in = num2date(time_in[:],time_in_units,calendar=in_calendar)
    dt_in_year = num2date(time_in[0],time_in_units,calendar=in_calendar).year

    for n in range(len(time_in)):
        if num2date(time_in[n],time_in_units,calendar=in_calendar).year == dt_in_year:
            data_max_len = n

    # add one count
    data_max_len = data_max_len + 1

    ## get start and stop date from in_file

    # get first value of array time
    dt_start_in = str(dt_in[0])
    dt_start_in = dt_start_in[:dt_start_in.index(' ')].replace('-','')

    # get last value of array time
    dt_stop_in = str(dt_in[data_max_len-1])
    dt_stop_in = dt_stop_in[:dt_stop_in.index(' ')].replace('-','')

    # now create the correct filename in temp directory
    # calculate time difference between first two time steps (in hours)
    # in hours: should be 1 or 3 or 6
    a = datetime.strptime(str(dt_in[0]), settings.FMT)
    b = datetime.strptime(str(dt_in[1]), settings.FMT)
    logger.debug("Start: %s, stop: %s" % (str(a),str(a)))

    tdelta = b - a
    tdelta_seconds = tdelta.seconds
    input_time_step = tdelta_seconds / 3600. + (tdelta.days * 24.)
    logger.debug("Input data time interval: %shourly" % (str(input_time_step)))

    #stop if year is not correct
    if str(a)[:4] != year:
        cmd= "File %s seems to be corrupt! The year from the filename is not the same as the year of the first data point %s! Skipping year..." % (in_file,str(a))
        logger.error(cmd)
        print(cmd)
        f_in.close()
        return reslist

    # difference one day: seconds of time delta are '0'!
    if tdelta_seconds == 0:
        tdelta_seconds = tdelta.days * 24 * 3600.
   # logger.info("Time starts at: %s, %s, difference (in seconds) is: %s" % (str(a),str(b),str(tdelta.seconds)))

    # define variables for storing the pathes for mrfso and mrso
    in_file_help = ""
    in_file_org = ""

    new_reslist=list(reslist) #remove resolutions from this list that are higher than the input data resolution
    # process all requested resolutions
    for res in reslist:

        if res in ["1hr","3hr","6hr","12hr"]:
            res_hr=(float(res[:-2])) #extract time resolution in hours
            cm_type = params[config.get_config_value('index','INDEX_VAR_CM_SUB')]
        elif res=="day":
            res_hr=24.
            cm_type = params[config.get_config_value('index','INDEX_VAR_CM_DAY')]
        elif res=="mon":
            res_hr= 28*24.  #minimum number of hours per month
            cm_type = params[config.get_config_value('index','INDEX_VAR_CM_MON')]
        elif res=="sem":
            res_hr= 28*24.*3  #minimum number of hours per season
            cm_type = params[config.get_config_value('index','INDEX_VAR_CM_SEM')]

        #check if requested time resolution is possible given the input time resolution
        if res_hr < input_time_step:
            logger.warning("Requested time resolution (%s) is higher than time resolution of input data (%s hr). Skip this resolution for all following files.." % (res,input_time_step))
            new_reslist.remove(res)
            continue

        # process only if cell method is definded in input matrix
        if cm_type != '':
            logger.info("#########################")
            logger.log(35,"     resolution: '%s'" % res)
            logger.debug("cell method: '%s' " % (cm_type))
            logger.info("#########################")

            #call method for seasonal mean

            if res=="sem":
                proc_seasonal_mean(params,year)
                continue

            # out directory

            outdir = get_out_dir(var,res)

            # get file name
            outfile = create_filename(var,res,dt_start_in,dt_stop_in,logger=logger)
            # create complete outpath: outdir + outfile
            outpath = "%s/%s" % (outdir,outfile)
            # skip file if exist

            if os.path.isfile(outpath):
                logger.info("Output file exists: %s" % (outpath))
                if not config.get_config_value('boolean','overwrite'):
                    logger.info("Skipping...")
                    continue
                else:
                    logger.info("Overwriting..")
            logger.debug("Output to: %s" % (outpath))

            # set step wide of cdo command
            if res == '1hr':
                selhour = "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23"
                nstep = 1. / (tdelta_seconds/3600.)
            elif res == '3hr':
                selhour = "0,3,6,9,12,15,18,21"
                nstep = 3. / (tdelta_seconds/3600.)
            # 6 hourly data
            elif res == '6hr':
                selhour = "0,6,12,18"
                nstep = 6. / (tdelta_seconds/3600.)
            # 12 hourly data
            elif res == '12hr':
                selhour = "0,12"
                nstep = 12. / (tdelta_seconds/3600.)
            # daily data
            elif res == 'day':
                nstep = 24. / (tdelta_seconds/3600.)
            # yearly data, consider calendar!!
            elif res == 'mon':
                if in_calendar in ('standard','gregorian','proleptic_gregorian','noleap','365_day','julian'):
                    nstep = 365. * 24. / (tdelta_seconds/3600.)
                elif in_calendar == '360_day':
                    nstep = 360. * 24. / (tdelta_seconds/3600.)
                elif in_calendar in ('366_day','all_leap'):
                    nstep = 366. * 24. / (tdelta_seconds/3600.)
            # TODO
            #elif res == 'sem':
                #if time.calendar in ('standard','gregorian','proleptic_gregorian','noleap','365_day','julian','all_leap'):
                    #nstep = (365 * 24 / (tdelta_seconds/3600)) / 4
                #elif time.calendar == '360_day':
                    #nstep = (360 * 24 / (tdelta_seconds/3600)) / 4
                #elif time.calendar == '366_day':
                    #nstep = (366 * 24 / (tdelta_seconds/3600)) / 4

            if params[config.get_config_value('index','INDEX_COVERT_FACTOR')] != '' and float(params[config.get_config_value('index','INDEX_COVERT_FACTOR')].strip().replace(',','.')) != 0 \
                    and float(params[config.get_config_value('index','INDEX_COVERT_FACTOR')].strip().replace(',','.')) != 1:
                cmd_mul = ' -mulc,%s ' % (params[config.get_config_value('index','INDEX_COVERT_FACTOR')].strip().replace(',','.'))
                # to use the time steps from input to correct the conversation factor
                # commented out for now!!
                # TODO
                if params[config.get_config_value('index','INDEX_FRE_AGG')] == 'i' or params[config.get_config_value('index','INDEX_FRE_AGG')] == '':
                    input_time_step = 1
                mulc_factor = float(params[config.get_config_value('index','INDEX_COVERT_FACTOR')].strip().replace(',','.')) / float(input_time_step)
                mulc_factor_str = str(mulc_factor)
                cmd_mul = ' -mulc,%s ' % (mulc_factor_str)
            else:
                cmd_mul = ""
            logger.debug("mulc factor for variable(%s): %s" % (var,cmd_mul))

            # create help output file which is at the zthe new in_file
            if var in ['mrso','mrfso'] and not os.path.isfile(in_file_help):
                cmd1 = "cdo enssum "
                # use only layer 1 to 8 for the output
                idx_from = 1
                # use value from table + 1 as upper limit for the soil levels e.g. 8 + 1 = 9!
                idx_to = int(params[config.get_config_value('index','INDEX_VAL_LEV')].strip()) + 1
                arr = {}
                for i in range(idx_from,idx_to):
                    f_hlp = tempfile.NamedTemporaryFile(dir=settings.DirWork,delete=False,suffix=year)
                    arr[i] = f_hlp.name
                    retval = shell("cdo -f %s sellevidx,%d %s %s" %(config.get_config_value('settings', 'cdo_nctype'),i,in_file,arr[i]))

                # now calculate the sum
                f_hlp = tempfile.NamedTemporaryFile(dir=settings.DirWork,delete=False,suffix=year)
                #write files in arr into str with whitespace separation for cdo command
                files_str=" ".join(arr.values())
                cmd = "%s %s %s" % (cmd1,files_str,f_hlp.name)
                retval = shell(cmd,logger=logger)
                # multiply with factor 1000 (from csv table)
                # switch from original in_file to the new in_file for these variables
                #in_file = "%s/%s-%s.nc" % (settings.DirWork,'help','1000')
                in_file_help = "%s/help-%s-%s-%s.nc" % (settings.DirWork,year,var,str(uuid.uuid1()))
#                in_file = tempfile.NamedTemporaryFile(dir=settings.DirWork)
                cmd = "cdo mulc,%d %s %s" % (int(params[config.get_config_value('index','INDEX_COVERT_FACTOR')]),f_hlp.name,in_file_help)
                retval = shell(cmd,logger=logger)
                # remove all help files
                os.remove(f_hlp.name)
                for i in range(idx_from,idx_to):
                    os.remove(arr[i])
                in_file_org = in_file
                in_file = in_file_help

            ftmp_name = "%s/%s-%s-%s.nc" % (settings.DirWork,year,str(uuid.uuid1()),var)
#
            # get type of function to create the output file: point,mean,maximum,minimum,sum
            # extract cell method from string
            t_delim = 'mean over days'
            if t_delim in cm_type:
                cm0 = cm_type[cm_type.index(' '):]
                cm = 'mean' #cm_type[cm_type.index(t_delim)+len(t_delim):]
                cmd = "Cell method used: %s" % (cm0)

            else:
                cm = cm_type

            # mulc has been already done before!!
            if var in ['mrso','mrfso']:
                cmd_mul = ""

            # 3 / 6 hourly data
            if res == '1hr' or res == '3hr' or res == "6hr":
                if cm == 'point':
                    cmd = "cdo -f %s -s selhour,%s %s %s %s" % (config.get_config_value('settings', 'cdo_nctype'),selhour,cmd_mul,in_file,ftmp_name)
                else:
                    cmd = "cdo -f %s -s timsel%s,%s %s %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,int(nstep),cmd_mul,in_file,ftmp_name)
            # daily data
            elif res == 'day':
                if cm in ['maximum','minimum']:
                    cm1 = cm[:3]
                else:
                    cm1 = cm
                # multiply with constant value from table (only if not 0)
                #if float(params[config.get_config_value('index','INDEX_COVERT_FACTOR].strip().replace(',','.')) != 0 and float(params[config.get_config_value('index','INDEX_COVERT_FACTOR].strip().replace(',','.')) != 1:
                    #cmd_mul = ' -mulc,%s ' % (params[config.get_config_value('index','INDEX_COVERT_FACTOR].strip().replace(',','.'))
                #else:
                    #cmd_mul = ""
                cmd = "cdo -f %s -s day%s %s %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm1,cmd_mul,in_file,ftmp_name)
            # monthy data
            elif res == 'mon':
                # get file with daily data from the same input (if exist)
                DayFile = create_filename(var,'day',dt_start_in,dt_stop_in,logger=logger)
                DayPath = "%s/%s" % (get_out_dir(var,'day'),DayFile)
                # use day files or prcess this step before
                if os.path.isfile(DayPath):
                    cmd = "cdo -f %s -s mon%s %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,DayPath,ftmp_name)
                else:
                    # day and mon: same cell methods (cm)
                    cmd = "cdo -f %s -s -mon%s -day%s %s %s %s" % (config.get_config_value('settings', 'cdo_nctype'),cm,cm,cmd_mul,in_file,ftmp_name)
            # do cmd
            retval = shell(cmd,logger=logger)


            ####################################################
            # open to output file
            ####################################################

            # open ftmp_name for reading
            f_tmp = Dataset(ftmp_name,'r')
            #print "Variables: ",f_tmp.variables.keys()

            # create object for output file
            f_out = Dataset(outpath,'w')

            # create dimensions in target file
            for name, dimension in f_tmp.dimensions.items():
                # skip list items
                if name in settings.varlist_reject:
                    continue
                    #f_out.createDimension(name, len(dimension) if not dimension.isunlimited() else None)
                else:
                    f_out.createDimension(name, len(dimension) if not dimension.isunlimited() else None)

            # set dimension vertices only if set to True in settings file
            if config.get_config_value('boolean','add_vertices') == True:
                f_out.createDimension('vertices',4)
                logger.info("Add vertices")

            # copy variables from temp file
            for var_name in f_tmp.variables.keys():
                # don't copy time_bnds if cm == point or variable time_bnds
                if cm == 'point' and var_name == 'time_bnds': # or var_name == 'pressure':
                    continue
                var_in = f_tmp.variables[var_name]
                # create output variable
                if var_name in ['rlon','rlat']:
                    data_type = 'd'
                elif var_name in ['lon','lat']:
                    data_type = 'd'
                elif var_name in settings.varlist_reject:
                    continue
                    #data_type = 'i8'
                else:
                    data_type = var_in.datatype
                # at variable creation set fill_vlue, later is impossible
                # also set the compression
                if config.get_config_value('boolean','nc_compress') == True:
                    logger.debug("COMPRESS variable: %s" % (var_name))

                # skip 'pressure'!!
                my_lst = []
                for dim in var_in.dimensions:
                    if str(dim) not in settings.varlist_reject:
                        my_lst.append(dim)
                var_dims = tuple(my_lst)
                logger.debug("Dimensions (of variable %s): %s" % (var_name,str(var_dims)))
                logger.debug("Attributes (of variable %s): %s" % (var_name,var_in.ncattrs()))
                if var_name in [var,settings.netCDF_attributes['RCM_NAME_ORG']]:
                    if config.get_config_value('boolean','nc_compress') == True:
                        var_out = f_out.createVariable(var_name,datatype=data_type,
                            dimensions=var_dims,complevel=4,fill_value=settings.netCDF_attributes['missing_value'])
                    else:
                        var_out = f_out.createVariable(var_name,datatype=data_type,
                            dimensions=var_dims,fill_value=settings.netCDF_attributes['missing_value'])
                    logger.debug("FillValue(output): %s,%s" % (var_name,var_out._FillValue))
                else:
                    if config.get_config_value('boolean','nc_compress') == True:
                        var_out = f_out.createVariable(var_name,datatype=data_type,dimensions=var_dims,complevel=4)
                    else:
                        var_out = f_out.createVariable(var_name,datatype=data_type,dimensions=var_dims)

                logger.debug("Dimensions (of variable %s): %s" % (var_name,str(f_out.dimensions)))
                # set all character fields as character converted with str() function
                # create attribute list
                if var_name in ['lat','lon']:
                    att_lst = get_attr_list(var_name)
                else:
                    att_lst = {}
                    for k in var_in.ncattrs():
                       # if k in ['_FillValue','missing_value','grid_north_pole_latitude','grid_north_pole_longitude']:
                        #    att_lst[k] = np.float32(var_in.getncattr(k))

                            #also set the respective other value
                         #   if k=='_FillValue':
                           #     att_lst['missing_value'] = np.float32(var_in.getncattr(k))
                          #  elif k=='missing_value':
                            #    att_lst['_FillValue'] = np.float32(var_in.getncattr(k))
                        #else:
                        att_lst[k] = var_in.getncattr(k)
                var_out.setncatts(att_lst)

                # copy content to new datatype
                var_out[:] = var_in[:]

                logger.debug("Copy from tmp: %s" % (var_out.name))
                if var_out.name == 'time':
                    if 'calendar' in var_out.ncattrs():
                        if var_out.getncattr('calendar') != in_calendar:
                            var_out.calendar = in_calendar
                        else:
                            var_out.calendar = str(var_out.getncattr('calendar'))
                    elif 'bounds' in var_out.ncattrs():
                        var_out.bounds = str(var_out.getncattr('bounds'))
                        var_out.setncattr('test_bounds1',var_out.getncattr('bounds'))
                        var_out.test_bounds2 = var_out.getncattr('bounds')
                    elif 'standard_name' in var_out.ncattrs():
                        var_out.standard_name = str(var_out.getncattr('standard_name'))

            # copy lon/lat and rlon/rlat from input if needed:
            for var_name in f_in.variables.keys():
                # take only the variables lat and lon
                if (var_name in ['lon','lat','rlon','rlat'] and var_name in f_in.variables.keys() and
                            var_name not in f_out.variables.keys() ):
                    var_in = f_in.variables[var_name]
                    #print "IN: ",var_name, var_in.dimensions
                    #print "OUT: ",var_name,f_out.dimensions()
                    j = 0
                    for var_dim in var_in.dimensions:
                        if var_dim not in f_out.dimensions:
                            #print "CREATE DIM ",var_dim,len(var_dim),len(var_in),var_in.shape[j]
                            f_out.createDimension(var_dim,size=var_in.shape[j])
                        j = j + 1
                    if var_name in ['rlon','rlat']:
                        data_type = 'd'
                    elif var_name in ['lon','lat']:
                        data_type = 'd'
                    elif var_name in settings.varlist_reject:
                        continue
                    # create output variable
                    var_out = f_out.createVariable(var_name,datatype=data_type,dimensions=var_in.dimensions)
                    # set all character fields as character converted with str() function
                    # create attribute list
                    if var_name in ['lat','lon']:
                        att_lst = get_attr_list(var_name)
                    else:
                        att_lst = {}
                        for k in var_in.ncattrs():
                            att_lst[k] = str(var_in.getncattr(k))
                    var_out.setncatts(att_lst)
                    # copy content to new datatype
                    var_out[:] = var_in[:]
                    logger.debug("Copy from input: %s" % (var_out.name))

            ##############################
            # now correct time,time_bnds #
            ##############################

            # get time and time_bnds variables from output
            time = f_out.variables['time']
            # only if not point
            if cm != 'point':
                time_bnds = f_out.variables['time_bnds']

            # get length of data array (== length of time array and length of time_bnds array
            try:
                data_len = f_out.variables[settings.netCDF_attributes['RCM_NAME_ORG']].shape[0]
            except:
                data_len = f_out.variables[settings.netCDF_attributes['cf_name']].shape[0]
            data_len = min(data_len,data_max_len)
            logger.debug("Date len: %s" % str(data_len))

            #TODO  use/no use of time_bnds??

            # get time_bnds variable from input
            if 'time_bnds' in f_in.variables.keys():
                time_bnds_in = f_in.variables['time_bnds']
                # get first time step in input file to distingish ref date
                date_start = num2date(time_bnds_in[0,0],time_in_units,in_calendar)
            else:
                date_start = num2date(time_in[0],time_in_units,in_calendar)

            # first time step
            #date_start = num2date(time_in[0],time_in_units,in_calendar)

            # check first lower time_bound if exist
            if date_start.year < dt_in_year:
                if 'time_bnds' in f_in.variables.keys():
                    # or first time_bound lower value
                    date_start = num2date(time_bnds_in[0,0],time_in_units,in_calendar)
                else:
                    # or second time step
                    date_start = num2date(time_in[1],time_in_units,in_calendar)
            # check first upper time_bound if exist
            if date_start.year < dt_in_year:
                if 'time_bnds' in f_in.variables.keys():
                    # or first time_bound higher value
                    date_start = num2date(time_bnds_in[0,1],time_in_units,in_calendar)

            # if year of first time step still not in actual year: search time steps until actual year
            n = 1
            while date_start.year < dt_in_year and n < len(time_in):
                # next time step
                date_start = num2date(time_in[n],time_in_units,in_calendar)
                # increment index
                n += 1

            # move the reference date to 1949-12-01T00:00:00Z
            # by setting time:units to: "days since 1949-12-01T00:00:00Z"
            time.units = config.get_config_value('settings','units')
            # now get the difference in time.units for refdate: start point for all settings in time and time_bnds
            num_refdate_diff = date2num(date_start,time.units,calendar=in_calendar)

            # show some numbers
            logger.debug("num_refdate_diff: %s" % str(num_refdate_diff))

            # start always with time = 00:00:00
            if date_start.hour > 0:
                num_refdate_diff = float(int(num_refdate_diff))
                logger.warning("Set time of start date (%s) to 00:00!" % str(date_start))


            if res == '1hr':
                num = 1. / 24.
                # set time and time_bnds
                if cm != 'point':
                    logger.debug("Start for time_bnds: %s, %s",str(num_refdate_diff),str(num2date(num_refdate_diff,time.units,time.calendar)))
                    for n in range(data_len):
                        time_bnds[n,0] = num_refdate_diff + (n * num)
                        time_bnds[n,1] = num_refdate_diff + ((n + 1) * num)
                        time[n] = (time_bnds[n,0] + time_bnds[n,1]) / 2.0
                else:
                    # set time
                    for n in range(data_len):
                        time[n] = num_refdate_diff + n * num
            elif res == '3hr':
                num = 0.125
                # set time and time_bnds
                if cm != 'point':
                    logger.info("Start for time_bnds: %s, %s",str(num_refdate_diff),str(num2date(num_refdate_diff,time.units,time.calendar)))
                    for n in range(data_len):
                        time_bnds[n,0] = num_refdate_diff + (n * num)
                        time_bnds[n,1] = num_refdate_diff + ((n + 1) * num)
                        time[n] = (time_bnds[n,0] + time_bnds[n,1]) / 2.0
                else:
                    # set time
                    for n in range(data_len):
                        time[n] = num_refdate_diff + n * num
            elif res == '6hr':
                num = 0.25
                # set time and time_bnds
                if cm != 'point':
                    logger.info("Start for time_bnds: %s, %s",str(num_refdate_diff),str(num2date(num_refdate_diff,time.units,time.calendar)))
                    for n in range(data_len):
                        time_bnds[n,0] = num_refdate_diff + (n * num)
                        time_bnds[n,1] = num_refdate_diff + ((n + 1) * num)
                        time[n] = (time_bnds[n,0] + time_bnds[n,1]) / 2.0
                else:
                    # set time
                    for n in range(data_len):
                        time[n] = num_refdate_diff + n * num
            elif res == '12hr':
                num = 0.5
                # set time and time_bnds
                if cm != 'point':
                    logger.info("Start for time_bnds: %s, %s",str(num_refdate_diff),str(num2date(num_refdate_diff,time.units,time.calendar)))
                    for n in range(data_len):
                        time_bnds[n,0] = num_refdate_diff + (n * num)
                        time_bnds[n,1] = num_refdate_diff + ((n + 1) * num)
                        time[n] = (time_bnds[n,0] + time_bnds[n,1]) / 2.0
                else:
                    # set time
                    for n in range(data_len):
                        time[n] = num_refdate_diff + n * num
            elif res == 'day':
                num = 1.
                for n in range(data_len):
                    time_bnds[n,0] = num_refdate_diff + (n * num)
                    time_bnds[n,1] = num_refdate_diff + ((n + 1) * num)
                    time[n] = (time_bnds[n,0] + time_bnds[n,1]) / 2.0
            # TODO, monthly settings
            elif res == 'mon':
                # n: 0,1,...11!!
                start = num_refdate_diff
                # only 12 month a year!!
                for n in range(data_len):
                    time_bnds[n,0] = num_refdate_diff
                    logger.debug("bnds1: %s" % (num2date(num_refdate_diff,time.units,calendar=in_calendar)))

                    #d = num2date(time[n],time.units,time.calendar)
                    d = num2date(num_refdate_diff,time.units,calendar=in_calendar)
                    # only 12 month!
                    m = n % 12
#                    print m,m+1,data_len,time.calendar,d
                    days = settings.dpm[time.calendar][m+1]
                    # add one day in February of leap year
                    if leap_year(d.year,time.calendar) and m == 1:
                        days += 1
                    logger.debug("Add DAYs: %d,%d,%d" % (days,d.year,d.month))

                    num_refdate_diff += days
                    logger.debug("bnds2: %s" % (num2date(num_refdate_diff,time.units,calendar=in_calendar)))
                    time_bnds[n,1] = num_refdate_diff
                    time[n] = (time_bnds[n,0] + time_bnds[n,1]) / 2.0
                end = num_refdate_diff
                logger.debug("time_bnds difference: %s" % (str(end - start)))

            # commit changes
            f_out.sync()

            ###################################
            # do some additional settings
            ###################################
            # rename variable
            try:
                f_out.renameVariable(settings.netCDF_attributes['RCM_NAME_ORG'],settings.netCDF_attributes['cf_name'])
            except:
                logger.debug("Variable has cf name already: %s" % (var))

            # no time_bnds if cell method is 'point'
            if cm == 'point':
                f_var = f_out.variables['time']
                try:
                    f_var.delncattr('bounds')
                except:
                    logger.info("Attribute %s not available for variable %s." % ('bounds','time'))

            if int(params[config.get_config_value('index','INDEX_VAL_LEV')].strip()) > 0 and not var in ['mrfso','mrro']:
                if params[config.get_config_value('index','INDEX_MODEL_LEVEL')] == config.get_config_value('settings','PModelType'):
                    if not 'plev' in f_out.variables:
                        var_out = f_out.createVariable('plev',datatype='d')
                        var_out.units = "Pa"
                        var_out.axis = "Z"
                        var_out.positive = "down"
                        var_out.long_name = "pressure"
                        var_out.standard_name = "air_pressure"
                        var_out[0] = params[config.get_config_value('index','INDEX_VAL_PLEV')]
                    # model level variable
                elif params[config.get_config_value('index','INDEX_MODEL_LEVEL')] == config.get_config_value('settings','MModelType'):
                    if not 'height' in f_out.variables:
                        var_out = f_out.createVariable('height',datatype='d')
                        var_out.units = "m"
                        var_out.axis = "Z"
                        var_out.positive = "up"
                        var_out.long_name = "height"
                        var_out.standard_name = "height"
                        var_out[0] = params[config.get_config_value('index','INDEX_VAL_HEIGHT')]

            # set all predefined global attributes
            if settings.Global_attributes=={}:
                logger.error("List of global attributes is empty!")
            else:
                f_out.setncatts(settings.Global_attributes)
                logger.info("Global attributes set!")

            # commit changes
            f_out.sync()

            # exist in some output (e.g. CCLM) in CORDEX, default: False
            if config.get_config_value('boolean','add_vertices') == True:
                add_vertices(f_out,logger=logger)

            # create variable object to output file
            f_var = f_out.variables[settings.netCDF_attributes['cf_name']]
            # set additional variables attributes
            f_var.standard_name = settings.netCDF_attributes['standard_name']
            f_var.long_name = settings.netCDF_attributes['long_name']
            f_var.units = settings.netCDF_attributes['units']
            f_var.cell_methods = "time: %s" % (cm_type)

            # check wether lon/lat exist
            if not 'lon' in f_out.variables or not 'lat' in f_out.variables:
                # add lon/lat
                add_coordinates(f_out,logger=logger)

            # set attribute coordinates
            set_coord_attributes(f_var,f_out)

            # set attribute missing_value
            f_var.missing_value = settings.netCDF_attributes['missing_value']

            try:
                f_var.setncattr('grid_mapping','rotated_pole')
            except Exception as e:
                logger.warning(str(e))

           # commit changes
            f_out.sync()

            #delete bounds dimension if not used:
            if ("bnds" in f_out.dimensions) and (cm_type=="point"):
                logger.info("Deleting unused bounds dimension")
                f_out.createVariable("help",datatype="d",dimensions=("bnds",))
                f_out.sync()
                f_out.close()
                cmd="ncks -x -v help -O %s %s" % (outpath,outpath)
                shell(cmd)
            else:
                # close output file
                f_out.close()

            # remove help file
            os.remove(ftmp_name)

            # set attributes: frequency,tracking_id,creation_date
            set_attributes_create(outpath,res,year,logger=logger)

            # ncopy file to correct output format
            if config.get_config_value('boolean','nc_compress') == True:
                compress_output(outpath,year,logger=logger)
            logger.info("Variable attributes set!")



        else:
            cmd = "No cell method set for this variable (%s) and time resolution (%s)." % (var,res)
            logger.warning(cmd)

    # ATTENTION: 'in_file' is only to be deleted here for these variables, otherwise it is read-only!!
    if var in ['mrso','mrfso'] and os.path.isfile(in_file_org):
        try:
            in_file = in_file_org
            os.remove(in_file_help)
        except:
            cmd = "Could not remove file: %s" % (in_file)
            logger.warning(cmd)


    # close input file
    f_in.close()
    # ready message
    return new_reslist

