#!/usr/bin/python
#
# configure programm
#
# Hans Ramthun
# DKRZ 2016, 2017
#
#
######################################################################################################
import logging
import pkg_resources
import os

#import csv

from _compat import PY2
if PY2:
    import ConfigParser
else:
    import configparser

RAW_OPTIONS = [('logging', 'format'), ]

CONFIG = None
#LOGGER = logging.getLogger("cmorlight")

# -----------------------------------------------------------------------------


def get_config_value(section, option, inifile=None):
    """Get desired value from  configuration files
    :param section: section in configuration files
    :type section: string
    :param option: option in the section
    :type option: string
    :returns: value found in the configuration file
    """

    if not CONFIG:
        print("Load configuration file first! Exiting...")
        exit

    value = ''

    if CONFIG.has_section(section):
        if CONFIG.has_option(section, option):
            raw = (section, option) in RAW_OPTIONS
            value = CONFIG.get(section, option, raw=raw)

            # Convert Boolean string to real Boolean values
            if value.lower() == "false":
                value = False
            elif value.lower() == "true":
                value = True

    if section == 'index':
        value = int(value)
    elif section == 'float':
        value = float(value)
    elif section == 'boolean':
        value = bool(value)
#    print value,type(value)
    return value


# -----------------------------------------------------------------------------
def get_model_value(section,option):
    ''' Get value from model section '''
    model = get_config_value('init','model')
    return get_config_value("settings_%s" % (model), option)


# -----------------------------------------------------------------------------
def set_config_value(section, option, value,inifile=None):
    ''' '''
    if not CONFIG:
        print("Load configuration file first! Exiting...")
        exit

    if not CONFIG.has_section(section):
        CONFIG.add_section(section)
    CONFIG.set(section, option, value)


# -----------------------------------------------------------------------------
def load_configuration(inifile):
    """Load PyWPS configuration from configuration files.
    The later configuration file in the array overwrites configuration
    from the first.
    :param cfgfiles: list of configuration files
    """
    global CONFIG

  #  LOGGER.info('loading configuration from %s' % inifile)
    if PY2:
        CONFIG = ConfigParser.SafeConfigParser()
    else:
        CONFIG = configparser.ConfigParser()

    CONFIG.add_section('init')
    CONFIG.set("init","inifile",inifile)
    CONFIG.readfp(open(pkg_resources.resource_filename(__name__,inifile)))
    #Extend input path if respective option is set:
    if CONFIG.get('boolean','extend_DirIn')=='True':
      DirIn=CONFIG.get('settings','DirIn')+'/'+CONFIG.get('settings_CCLM','driving_model_id')+'/'+CONFIG.get('settings_CCLM','driving_experiment_name')
      CONFIG.set('settings','DirIn',DirIn)

