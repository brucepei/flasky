import sys
import re
import os
import logging
import logging.handlers
import Queue
import multiprocessing
from subprocess import Popen, PIPE, check_output
import time
from pysnmp.hlapi import *

try:
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

log = logging.getLogger(__name__)
log.addHandler(NullHandler())

def add_stderr_logger(level=logging.DEBUG):
    # This method needs to be in this __init__.py to get the __name__ correct
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.debug('Added a stderr logging handler to logger: %s' % __name__)
    return logger

def add_file_logger(filename='monitor_mdm.log', level=logging.DEBUG):
    # This method needs to be in this __init__.py to get the __name__ correct
    logger = logging.getLogger(__name__)
    handler = logging.handlers.RotatingFileHandler(filename=filename, mode='a', maxBytes=2000000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s'))
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.debug('Added a file %s logging handler to logger: %s' % (filename, __name__))
    return logger

class Runner(object):
    default_timeout = 60
    
    @classmethod
    def fork(cls, cmd, input=None, timeout=default_timeout):
        log.debug("current pid {}".format(os.getpid()))
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=cls.popen, args=(q, cmd, input))
        p.start()
        log.debug("fork child process pid {}".format(p.pid))
        log.debug("join child process pid {} with timeout {}".format(p.pid, timeout))
        p.join(timeout)
        while p.is_alive():
            log.debug("Process {} timeout! Terminating...".format(p.pid))
            p.terminate()
            p.join(1)
        out, err = (None, None)
        try:
            out, err = q.get_nowait()
        except Queue.Empty:
            log.debug("Cannot get stdout/stderr: no response until exit!")
        log.debug("fork return output: {}".format(out))
        log.debug("fork return error: {}".format(err))
        log.debug("Process has been done!")
        return (out, err)
        
    @classmethod
    def popen(cls, q, cmd, input=None):
        log = add_stderr_logger()
        add_file_logger(filename='child.log')
        log.debug("Run popen in pid {}".format(os.getpid()))
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        log.debug("popen '{}' with child process pid {}".format(cmd, p.pid))
        out, err = p.communicate(input)
        log.debug("popen output: {}".format(out))
        if err:
            log.debug("popen error: {}".format(err))
        q.put((out, err))

class Monitor(object):
    wlan_intf_regex = re.compile(r'wlan[01]')
    wlan_conf_regex = re.compile(r'/etc/[^\/\s]*.conf')
    wlan_detect_interval = 60
    default_wlan_fail_times = 5
    default_no_wlan_times = 60
    
    @classmethod
    def check_wlan(cls):
        intfs, err = Runner.fork("adb shell ifconfig ^| grep wlan ^| grep -v grep")
        check_ok = None
        if err:
            log.error("Failed to get interface list: {}".format(err))
        else:
            intf_set = list()
            for m in cls.wlan_intf_regex.finditer(intfs):
                log.debug("Find wlan interface: {}".format(m.group(0)))
                intf_set.append(m.group(0))
            if intf_set:
                check_ok = 1
                log.debug("Found {} wlan interface, check the related process!".format(len(intf_set)))
                hostapd_ps, err = Runner.fork("adb shell ps -ef ^| grep 'hostapd\^|wpa_supplicant' ^| grep -v 'grep\^|hostapd_cli\^|wpa_cli'")
                if err:
                    log.error("Failed to get hostapd/wpa_supplicant process: {}".format(err))
                else:
                    conf_set = list()
                    for m in cls.wlan_conf_regex.finditer(hostapd_ps):
                        log.debug("Find wlan process with configuration: {}".format(m.group(0)))
                        conf_set.append(m.group(0))
                    conf_num = len(conf_set)
                    intf_num = len(intf_set)
                    if conf_num == intf_num:
                        log.error("WLAN configurations number equal with interfaces number {}".format(intf_num))
                        for conf in conf_set:
                            if conf == '/etc/hostapd.conf':
                                if 'wlan0' in intf_set:
                                    log.debug("OK: Found hostapd.conf, and wlan0 also exists!")
                                else:
                                    check_ok = 0
                                    log.error("NOK: Found hostapd.conf, but no wlan0!")
                            elif conf == '/etc/hostapd-wlan1.conf':
                                if 'wlan1' in intf_set:
                                    log.debug("OK: Found hostapd-wlan1.conf, and wlan1 also exists!")
                                else:
                                    check_ok = 0
                                    log.error("NOK: Found hostapd-wlan1.conf, but no wlan1!")
                            elif conf == '/etc/sta_mode_hostapd.conf':
                                if 'wlan1' in intf_set:
                                    log.debug("OK: Found sta_mode_hostapd.conf, and wlan1 also exists!")
                                else:
                                    check_ok = 0
                                    log.error("NOK: Found sta_mode_hostapd.conf, but no wlan1!")
                            elif conf == '/etc/wpa_supplicant.conf':
                                if 'wlan0' in intf_set:
                                    log.debug("OK: Found wpa_supplicant.conf, and wlan0 also exists!")
                                else:
                                    check_ok = 0
                                    log.error("NOK: Found wpa_supplicant.conf, but no wlan0!")
                            else:
                                log.warn("Got unexpect configuration file {}!".format(conf))
                    else:
                        check_ok = 0
                        log.error("WLAN configurations number {} not equal with interfaces number {}".format(conf_num, intf_num))
        log.debug("Check result: {}".format(check_ok))
        return check_ok

    @classmethod
    def pdu_control(cls, pdu_type, pdu_ip, pdu_port, pdu_switch):
        if pdu_type == 'cpc':
            return cls.pdu_cpc_control(pdu_ip, pdu_port, pdu_switch)
        else:
            log.error("Unspport PDU {} type!".format(pdu_type))

    @classmethod
    def usb_control(cls, usb_ip, usb_port, usb_switch):
        set_ok = 0
        control_script = r'C:\mdm_scripts\ac.pl'
        if not os.path.isfile(control_script):
            log.error("Not found usb controller script {}!".format(control_script))
            return set_ok
        usb_switch = 'on' if usb_switch else 'off'
        output = check_output(r'perl C:\mdm_scripts\ac.pl {} usb {} {}'.format(usb_ip, usb_port, usb_switch), shell=True)
        if output.find('SUCCESS') > -1:
            set_ok = 1
            log.debug("Set usb {}:{} {} success: {}".format(usb_ip, usb_port, usb_switch, output))
        else:
            log.debug("Set usb {}:{} {} failed: {}".format(usb_ip, usb_port, usb_switch, output))
        return set_ok

    @classmethod
    def pdu_cpc_control(cls, pdu_ip, pdu_port, pdu_switch):
        set_ok = 0
        pdu_switch = 'ON' if pdu_switch else 'OFF'
        errorIndication, errorStatus, errorIndex, varBinds = next(
            setCmd(
                SnmpEngine(),
                CommunityData('public', mpModel=0),
                UdpTransportTarget((pdu_ip, 161)),
                ContextData(),
                ObjectType(ObjectIdentity('.1.3.6.1.4.1.30966.10.2.4.{}.0'.format(pdu_port)), OctetString(pdu_switch)),
                lookupMib=False,
            )
        )
        if errorIndication:
            log.error("Failed to set CPC {}:{} {}, snmp engine error: {}!".format(pdu_ip, pdu_port, pdu_switch, errorIndication))
        elif errorStatus:
            log.debug('Failed to set CPC {}:{} {}, snmp agent error: {} at {}!'.format(errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex)-1][0] or '?'
                )
            )
        else:
            for varBind in varBinds:
                log.debug("SNMP set: {}".format(' = '.join([ x.prettyPrint() for x in varBind ])))
                if varBind[-1] == pdu_switch:
                    set_ok = 1
                    log.debug("Set CPC {}:{} {} succss!".format(pdu_ip, pdu_port, pdu_switch))
        return set_ok
                    
    @classmethod
    def monitor_wlan(cls, pdu_ip, pdu_port, usb_ip, usb_port, pdu_type='cpc', max_wlan_fail=default_wlan_fail_times, max_no_wlan=default_no_wlan_times):
        wlan_fail_times = 0
        no_wlan_times = 0
        log.debug("Start to monitor wlan status:\n\tCheck interval={}\n\tMax WLAN failure times={}\n\tMAX NO WLAN times={}".format(
                cls.wlan_detect_interval,
                max_wlan_fail,
                max_no_wlan,
            )
        )
        while True:
            wlan_status = cls.check_wlan()
            if wlan_status is None:
                wlan_fail_times = 0
                no_wlan_times += 1
                log.debug("Not found WLAN times: {}".format(no_wlan_times))
            elif wlan_status:
                wlan_fail_times = 0
                no_wlan_times = 0
                log.debug("WLAN status ok!")
            else:
                no_wlan_times = 0
                wlan_fail_times += 1
                log.debug("WLAN failed times: {}".format(wlan_fail_times))
            if no_wlan_times > max_no_wlan:
                log.error("Not found WLAN for a long time, restart PC")
                wlan_fail_times = 0
                no_wlan_times = 0
            elif wlan_fail_times > max_wlan_fail:
                log.error("WLAN failed for a long time, restart MDM")
                cls.pdu_control(pdu_type, pdu_ip, pdu_port, 0)
                cls.usb_control(usb_ip, usb_port, 0)
                log.debug("Power off PDU and USB, wait for some time")
                time.sleep(30)
                cls.pdu_control(pdu_type, pdu_ip, pdu_port, 1)
                cls.usb_control(usb_ip, usb_port, 1)
                log.debug("Power on PDU and USB, wait for some time")
                time.sleep(30)
                wlan_fail_times = 0
                no_wlan_times = 0
            log.debug("Waiting for next check loop...")
            time.sleep(cls.wlan_detect_interval)
            
if __name__ == '__main__':
    add_stderr_logger()
    add_file_logger()
    # if len(sys.argv) < 2:
        # log.error("Please specify the command!")
        # sys.exit(-1)
    # Runner.fork(*sys.argv[1:])
    Monitor.monitor_wlan(pdu_ip='192.168.3.12', pdu_port=1, usb_ip='192.168.3.32', usb_port=1, max_wlan_fail=3, max_no_wlan=3)

    
