#!/usr/bin/env python

import subprocess

from project_conf import fabconf

if len(fabconf['EC2_INSTANCES']) == 0:
    print "Error: you need to add the instance domain name to project_conf.py"
else:
    cmd = 'ssh -i ~/.ssh/%s %s@%s' % (fabconf['EC2_KEY_NAME'], fabconf['SERVER_USERNAME'], fabconf['EC2_INSTANCES'][0])
    print cmd
    subprocess.call(cmd,shell=True)

