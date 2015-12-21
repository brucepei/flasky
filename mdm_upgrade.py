import os
import sys
import re
import time
from subprocess import check_call, check_output
from requests import Session

build_list_url = r'http://127.0.0.1:5000/build/list'
project_name = 'MDM.LE.1.0'

def choose_build(build_list, user_choice=None):
    index = 1
    print "There are following builds:"
    for build in build_list:
        print "\t{}. {}\t{}".format(index, build['version'], build['name'])
        index += 1
    build_num = len(build_list)
    choice = user_choice
    while True:
        try:
            if choice is None:
                choice = input("Please choose a build to upgrade:")
            else:
                choice = int(choice)
        except Exception:
            print "Input error '{}', retry!".format(choice)
            continue
        if not isinstance(choice, int):
            print "Not integer '{}', retry!".format(choice)
            choice = None
        if choice > build_num or choice <= 0:
            print "Excceds the boundary '{}', retry!".format(choice)
            choice = None
        else:
            break
    return build_list[choice-1]

def get_build_list(url, project_name):
    sess = Session()
    resp = sess.post(url, params={'project_name': project_name})
    build_list = None
    try:
        build_list = resp.json()
        if build_list['code']:
            raise ValueError("Query failed: {}!".format(build_list['result']))
        else:
            build_list = build_list['result']
        # print build_list
    except Exception as err:
        raise ValueError("Failed to parse build list information: {}!".format(err))
    return build_list

def upgrade_mdm(build):
    crm_path = build['meta_path'];
    map_dir = 'z:';
    if os.path.isdir(map_dir):
        check_call("net use $map_dir /D /y")
    check_call("net use {} {}".format(map_dir, crm_path))
    if os.path.isdir(map_dir):
        print "Map to {} successfully!".format(map_dir)
    print "Reboot to bootloader"
    check_call("adb reboot bootloader")
    print "waiting for fastboot..."
    time.sleep(5)
    fastboot_output = ''
    regex_empty = re.compile(r'^\s*$')
    while regex_empty.match(fastboot_output):
        fastboot_output = check_output('fastboot devices')
        print "Fastboot no device, retry later..."
        time.sleep(2)
    print "Fastboot ready: '{}'".format(fastboot_output)
    os.chdir( os.path.join(map_dir, 'common', 'build') )
    check_call("python fastboot_complete.py")
    print "Done, enter to reboot!"
    raw_input()
    check_call("fastboot reboot")
    check_call("net use {} /D /y".format(map_dir))
    print "All jobs done!"

if __name__ == '__main__':
    build_list = get_build_list(build_list_url, project_name)
    build_choice = None
    if len(sys.argv) > 1:
        build_choice = sys.argv[1]
        print "User specify build number: {}".format(build_choice)
    build = choose_build(build_list, build_choice)
    print "Ready to burn build:\n\tversion: {}\n\tmeta: {}\n\tcrash: {}\n\tis crm: {}".format(build['version'], build['meta_path'], build['crash_path'], build['is_crm'])
    upgrade_mdm(build)