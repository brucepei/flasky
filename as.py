#coding=utf-8
import sys
import os
import socket
import threading
from subprocess import Popen, PIPE
import traceback
import getopt

opts, args = getopt.getopt(sys.argv[1:], "hp:l:",["help","port=","max_connection="])

max_connection=50
port=8001

def usage():
    print """
    -h --help             print the help
    -m --max_connection   Maximum number of connections
    -p --port             To monitor the port number
    """

for op, value in opts:
    if op in ("-m", "--max_connection"):
        max_connection = int(value)
    elif op in ("-p", "--port"):
        port = int(value)
    elif op in ("-h"):
        usage()
        sys.exit()

def run_remote_cmd(client, address):
    try:
        client.settimeout(500)
        buf = client.recv(4096)
        print '{0} received: {1}!'.format(address, buf)
        try:
            print '{0} run {1}'.format(address, buf.split())
            p = Popen(buf.split(), stdout=PIPE, stderr=PIPE)
            outputs, errors = p.communicate()
            print '{0} cmd output: {1}; error: {2}!'.format(address, outputs, errors)
        except Exception as err:
            client.send("cmd failed: {0}".format(err))
            print '{0} cmd error: {1}!'.format(address, traceback.print_exc())
    except socket.timeout:
        print '{0} time out!'.format(address)
    print '{0} disconnected!'.format(address)
    client.close()

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
    sock.bind(('localhost', port))  
    sock.listen(max_connection)
    print 'Server started at tcp port {0}!'.format(port)
    while True:  
        client,address = sock.accept()
        print '{0} connected!'.format(address)
        thread = threading.Thread(target=run_remote_cmd, args=(client, address))
        thread.start()

def test(cmd):
    thread = threading.Thread(target=run, args=(cmd,))
    thread.start()
    print "start thread"
    thread.join()
    print "end thread"

def run(cmd):
    p = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    outputs, errors = p.communicate()
    print 'output: {0}; error: {1}!'.format(outputs, errors)
    
if __name__ == '__main__':
    #test("ping 127.0.0.1 -n 3")
    main()