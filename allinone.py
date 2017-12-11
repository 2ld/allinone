#!/usr/bin/env python
# coding=utf-8

from __future__ import print_function

import logging
import multiprocessing
import os
import random
import re
import shutil
import subprocess
import uuid
from logging.config import dictConfig

import libvirt
import ruamel.yaml
import yaml
from ruamel.yaml.util import load_yaml_guess_indent

ALLINONE = 'allinone_test'

LOG_PATH = '/var/log/allinone.log'


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
            'StreamHandler': {'class': 'logging.StreamHandler',
                              'formatter': 'f',
                              'level': logging.INFO},
            'FileHandler': {
                'class': 'logging.FileHandler',
                'formatter': 'f',
                'level': logging.INFO,
                'filename': '%s' % LOG_PATH
            }
        },
        root={
                'handlers': ['StreamHandler', 'FileHandler'],
                'level': logging.DEBUG,
                },
    )
    dictConfig(dict_config)
    logger = logging.getLogger('allinone')
    return logger


logger = get_logger()


def restart_cobbler():
    """
    Restart cobbler after fuel astute file changed.
    """
    logger.info("-"*18 + " restart cobbler " + "-"*18)
    logger.info("Restart cobbler after network changed.")
    result = change_astute()
    if result:
        restart_command = "dockerctl restart cobbler"
        check_command = "dockerctl check cobbler"
        subprocess.call(restart_command, shell=True)
        output = subprocess.check_call(check_command, shell=True)
        if output == 0:
            logger.info("Cobbler is ready to go.")
            return True


def get_pxe_info():
    """
    Get the pxe interface from fuel astute yaml file.
    """
    with open("/etc/fuel/astute.yaml", 'r') as astute_file:
        cfg = yaml.load(astute_file)
    interface = cfg['ADMIN_NETWORK']['interface']
    return interface


def restart_network(pxe_info):
    """
    Restart network after interface change to bridge.
    """
    logger.info("-"*18 + " restart network " + "-"*18)
    logger.info("Restart network after net interface and astute file changed.")
    logger.info("The pxe interface is: %s" % pxe_info)
    result = change_pxe_to_bridge(pxe_info)
    if result:
        sys_command = 'systemctl restart network'
        man_command = 'ifup br0'
        exit_code = subprocess.call(sys_command, shell=True)
        if exit_code != 0:
            logger.info("Failed to bring br0 up by systemd, try to bring"
                        " bridge interfaces up by ifup.")
            output = subprocess.call(man_command, shell=True)
            if output == 0:
                logger.info("Success to bring br0 up by ifup.")
            else:
                logger.info("Failed to bring br0 up by ifup.")


def change_pxe_to_bridge(interface):
    """
    Change pxe interface to bridge br0.
    """
    # backup pxe network interface config file
    base = '/etc/sysconfig/network-scripts/ifcfg-'
    src = base + interface
    dst = src + '.orig'
    br_interface = base + 'br0'
    shutil.copyfile(src, dst)

    # remove ipaddress and netmask in pxe network interface config file
    f = open(src, 'r+')
    lines = f.readlines()
    f.seek(0)
    for line in lines:
        if not line.startswith('IPADDR') and not line.startswith('NETMASK'):
            f.write(line)
    f.write("BRIDGE=br0\n")
    f.truncate()
    f.close

    # create bridge br0 config file
    shutil.copyfile(dst, br_interface)
    f = open(br_interface, 'r+')
    lines = f.readlines()
    f.seek(0)
    flag = False
    for line in lines:
        line = line.replace(interface, 'br0')
        if line.lower().__contains__('type'):
            flag = True
            line = line.replace('Ethernet', 'Bridge')
        f.write(line)
    if not flag:
        line = 'TYPE=Bridge\n'
        f.write(line)
    f.truncate()
    f.close()
    return True


def change_astute():
    """
    Change fuel astute yaml file interface from linux interface to br0.
    """
    astute_path = '/etc/fuel/astute.yaml'
    yml_obj, ind, bsi = load_yaml_guess_indent(open(astute_path))
    yml_obj['ADMIN_NETWORK']['interface'] = 'br0'

    ruamel.yaml.round_trip_dump(yml_obj, open(astute_path, 'w'),
                                indent=ind, block_seq_indent=bsi)
    return True


def get_free_disk():
    """
    Find free disk under var in the filesystem, using 60%(round off) of the
    free disk as the vm's volume size. Format type in gigabytes.
    """
    df = subprocess.Popen(["df", "/var/"], stdout=subprocess.PIPE)
    output = df.communicate()[0]
    free_disk = output.split("\n")[1].split()[3]
    available_disk = int(round(int(free_disk) * 0.6 / 1024 / 1024))
    return available_disk


def get_free_mem():
    """
    Extract free mem on system, using 60%(round off) of the free mem as the
    the vm's mem size. Format type in gigabytes.
    """
    mem = subprocess.Popen(["free", "-h"], stdout=subprocess.PIPE)
    output = mem.communicate()[0]
    free_mem = output.split("\n")[1].split()[3]
    pattern = '[A-Za-z]'
    available_mem = int(round(int(re.sub(pattern, '', free_mem)) * 0.6))
    unit = re.search(pattern, free_mem).group(0)
    return {'size': available_mem, 'unit': unit}


def get_free_cpu():
    """
    Extract all cpus on system, using 60%(round off) of the all cpu as the
    vm' cpu numbers. Format type in integer.
    """

    all_cpu = multiprocessing.cpu_count()
    available_cpu = int(round(all_cpu * 0.6))
    return available_cpu


def randomMAC():
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, mac))


def get_domain_xml():
    """Define the domain xml file."""
    mem = get_free_mem()
    cpu = get_free_cpu()

    domain_xml = """
    <domain type='kvm' id='3'>
      <name>allinone</name>
      <uuid>%(generator_uuid)s</uuid>
      <memory unit='%(unit)s'>%(memory_size)s</memory>
      <vcpu placement='static'>%(cpu_count)s</vcpu>
      <resource>
        <partition>/machine</partition>
      </resource>
      <os>
        <type arch='x86_64' machine='pc-i440fx-rhel7.0.0'>hvm</type>
        <bootmenu enable='yes'/>
      </os>
      <features>
        <acpi/>
        <apic/>
      </features>
      <cpu mode='custom' match='exact'>
        <model fallback='allow'>SandyBridge</model>
      </cpu>
      <clock offset='utc'>
        <timer name='rtc' tickpolicy='catchup'/>
        <timer name='pit' tickpolicy='delay'/>
        <timer name='hpet' present='no'/>
      </clock>
      <on_poweroff>destroy</on_poweroff>
      <on_reboot>restart</on_reboot>
      <on_crash>restart</on_crash>
      <pm>
        <suspend-to-mem enabled='no'/>
        <suspend-to-disk enabled='no'/>
      </pm>
      <devices>
        <emulator>/usr/libexec/qemu-kvm</emulator>
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2'/>
          <source file='/var/lib/libvirt/images/allinone.qcow2'/>
          <backingStore/>
          <target dev='vda' bus='virtio'/>
          <boot order='2'/>
          <alias name='virtio-disk0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x08' \
              function='0x0'/>
        </disk>
        <controller type='usb' index='0' model='ich9-ehci1'>
          <alias name='usb'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x07' \
              function='0x7'/>
        </controller>
        <controller type='usb' index='0' model='ich9-uhci1'>
          <alias name='usb'/>
          <master startport='0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x07' \
              function='0x0' multifunction='on'/>
        </controller>
        <controller type='usb' index='0' model='ich9-uhci2'>
          <alias name='usb'/>
          <master startport='2'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x07' \
              function='0x1'/>
        </controller>
        <controller type='usb' index='0' model='ich9-uhci3'>
          <alias name='usb'/>
          <master startport='4'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x07' \
              function='0x2'/>
        </controller>
        <controller type='pci' index='0' model='pci-root'>
          <alias name='pci.0'/>
        </controller>
        <controller type='virtio-serial' index='0'>
          <alias name='virtio-serial0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x06' \
              function='0x0'/>
        </controller>
        <interface type='bridge'>
          <mac address='%(mac)s'/>
          <source bridge='br0'/>
          <target dev='vnet0'/>
          <model type='virtio'/>
          <boot order='1'/>
          <alias name='net0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x03' \
              function='0x0'/>
        </interface>
        <serial type='pty'>
          <source path='/dev/pts/4'/>
          <target port='0'/>
          <alias name='serial0'/>
        </serial>
        <console type='pty' tty='/dev/pts/4'>
          <source path='/dev/pts/4'/>
          <target type='serial' port='0'/>
          <alias name='serial0'/>
        </console>
        <channel type='spicevmc'>
          <target type='virtio' name='com.redhat.spice.0' state='disconnected'/>
          <alias name='channel0'/>
          <address type='virtio-serial' controller='0' bus='0' port='1'/>
        </channel>
        <input type='mouse' bus='ps2'>
          <alias name='input0'/>
        </input>
        <graphics type='spice' port='5903' autoport='yes' listen='0.0.0.0'>
          <listen type='address' address='0.0.0.0'/>
        </graphics>
        <sound model='ich6'>
          <alias name='sound0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x05' \
              function='0x0'/>
        </sound>
        <video>
          <model type='qxl' ram='65536' vram='65536' vgamem='16384' \
              heads='1' primary='yes'/>
          <alias name='video0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' \
              function='0x0'/>
        </video>
        <redirdev bus='usb' type='spicevmc'>
          <alias name='redir0'/>
          <address type='usb' bus='0' port='1'/>
        </redirdev>
        <redirdev bus='usb' type='spicevmc'>
          <alias name='redir1'/>
          <address type='usb' bus='0' port='2'/>
        </redirdev>
        <memballoon model='virtio'>
          <alias name='balloon0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x09' \
              function='0x0'/>
        </memballoon>
      </devices>
      <seclabel type='dynamic' model='dac' relabel='yes'>
        <label>+107:+107</label>
        <imagelabel>+107:+107</imagelabel>
      </seclabel>
      </domain>""" % {'generator_uuid': str(uuid.uuid4()),
                      'unit': mem['unit'],
                      'memory_size': mem['size'],
                      'cpu_count': cpu,
                      'mac': randomMAC()}

    return domain_xml


def create_vol():
    """Create the volume via qemu-img command."""
    vol_size = get_free_disk()
    command = "qemu-img create -f qcow2 \
    /var/lib/libvirt/images/allinone.qcow2 %sG" % vol_size
    output = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    result = output.communicate()
    if result[1] is None:
        logger.info("Creating a disk for VM: %s" % result[0])
        return True
    else:
        logger.error('Creating disk is failed，the reason is: %s' % result[1])
        raise Exception(
            "Creating disk is failed, the reason is: %s" %
            result[1])


def create_domain():
    """Create the instance from domain xml file."""
    domain_xml = get_domain_xml()

    conn = libvirt.open('qemu:///system')
    if conn is None:
        logger.info('Can not connect qemu:///system。')
        return False

    dom = conn.defineXML(domain_xml)
    if dom is None:
        logger.info('Can not create VM by XML。')
        return False

    logger.info('Creating VM '+dom.name()+' is successful。')

    conn.close()
    return True


def boot_instance():
    """
    Create the volume and boot the instance.
    """
    is_vol = create_vol()
    if is_vol:
        create_domain()
    else:
        logger.info('Creating disk is failed。')


def init_env():
    """
    init the environment: change pxe network interface to bridge,
    fuel astute yaml file , and restart network and cobbler.
    """
    pxe_info = get_pxe_info()
    restart_network(pxe_info)
    restart_cobbler()
    boot_instance()


if __name__ == "__main__":
    init_env()
