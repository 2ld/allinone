#!/usr/bin/env python
# coding=utf-8
import logging
import os
import sys
from argparse import ArgumentParser
from logging.config import dictConfig

import libvirt

ALLINONE = 'allinone'

LOG_PATH = '/var/log/allinone.log'


def libvirt_callback(userdata, err):
    '''
    Avoiding console prints by Libvirt Qemu python APIs
    '''
    pass


libvirt.registerErrorHandler(f=libvirt_callback, ctx=None)


def get_logger():
    if not os.path.isfile(LOG_PATH):
        os.mknod(LOG_PATH)
    dict_config = dict(
        version=1,
        formatters={
            'f': {'format':
                  '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'}
        },
        handlers={
            'FileHandler': {
                'class': 'logging.FileHandler',
                'formatter': 'f',
                'level': logging.INFO,
                'filename': '%s' % LOG_PATH
            }
        },
        root={
                'handlers': ['FileHandler'],
                'level': logging.DEBUG,
                },
    )
    dictConfig(dict_config)
    logger = logging.getLogger('allinone')
    return logger


logger = get_logger()


def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    try:
        conn = libvirt.open('qemu:///system')
    except Exception:
        logger.error('Sorry, libvirt failed to open a connection'
                     'to the hypervisor software')
        sys.exit('{"1001":"Sorry, libvirt failed to open a connection'
                 ' to the hypervisor software"}'
                 )
    return conn


def list_active_vms():
    '''
    Return a list of names for active virtual machine on the minion
    CLI Example::
        virsh list
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDomainsID():
        vms.append(conn.lookupByID(id_).name())
    return vms


def list_inactive_vms():
    '''
    Return a list of names for inactive virtual machine on the minion
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDefinedDomains():
        vms.append(id_)
    return vms


def list_vms():
    '''
    Return a list of virtual machine names on the minion
    CLI Example::
        virsh list --all
    '''
    vms = []
    vms.extend(list_active_vms())
    vms.extend(list_inactive_vms())
    return vms


def _get_dom(vm_):
    '''
    Return a domain object for the named vm
    '''
    conn = __get_conn()
    if vm_ not in list_vms():
        logger.error('The specified vm is not present')
        sys.exit('{"1002":"The specified vm is not present"}')
    return conn.lookupByName(vm_)


def create(vm_):
    '''
    Start a defined domain

    CLI Example:
        virsh start <vm name>
    '''
    dom = _get_dom(vm_)
    if dom.isActive() == 1:
        logger.error('The vm is already running')
        sys.exit('{"1005":"The vm is already running"}')
    try:
        success = dom.create()
        return dom, success
    except Exception:
        logger.error('libvirt failed to start vm')
        sys.exit('{"1003":"libvirt failed to start vm"}')


def destroy(vm_):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the
    power
    CLI Example:
        virsh destroy <vm name>
    '''
    dom = _get_dom(vm_)
    try:
        success = dom.destroy()
        return dom, success
    except Exception:
        logger.error('libvirt failed to stop vm')
        sys.exit('{"1004":"libvirt faild to stop vm"}')


def set_auto_start(vm_, dom, state='on'):
    '''
    Set domain auto start when host restart
    '''
    if state == 'on':
        return dom.setAutostart(1) == 0
    elif state == 'off':
        return dom.setAutostart(0) == 0
    else:
        return False


def start_domain():
    """start the instance."""
    dom, create_bool = create(ALLINONE)
    logger.info('VM ' + ALLINONE + ' is running now')
    if not set_auto_start(ALLINONE, dom, 'on'):
        logger.info('VM ' + ALLINONE + ' cant\'t set auto restart')
        return False
    logger.info('VM ' + ALLINONE + ' set auto restart success')
    return True


def stop_domain():
    """stop the instance."""
    dom, stop_bool = destroy(ALLINONE)
    logger.info('VM ' + ALLINONE + ' stop is successful')
    if not set_auto_start(ALLINONE, dom, 'off'):
        logger.info('VM ' + ALLINONE + ' can\'t stop auto restart')
        return False
    logger.info('VM ' + ALLINONE + ' stop auto restart success')
    return True


def get_parser():
    """
    Get parser object for allinone
    """
    parser = ArgumentParser()
    parser.add_argument("--start-vm",
                        action="store_true",
                        help="start VM")
    parser.add_argument("--stop-vm",
                        action="store_true",
                        help="stop VM")
    return parser


def main(parser):
    """
    Parser the args.
    """
    args = parser.parse_args()
    if args.start_vm:
        start_domain()
        sys.exit('{"1000":"This operation was successful"}')
    elif args.stop_vm:
        stop_domain()
        sys.exit('{"1000":"This operation was successful"}')
    else:
        parser.error("You must specify the option - either via,"
                     " --start-vm, or --stop-vm!")


if __name__ == "__main__":
    parser = get_parser()
    main(parser)
