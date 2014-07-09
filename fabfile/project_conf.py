''' 
--------------------------------------------------------------------------------------
project_conf.py
--------------------------------------------------------------------------------------
Configuration settings that detail your EC2 instances and other info about your Django
servers

author : Ashok Fernandez (github.com/ashokfernandez/)
credit : Derived from files in https://github.com/gcollazo/Fabulous
date   : 11 / 3 / 2014

Make sure you fill everything out that looks like it needs to be filled out, there are links 
in the comments to help.
'''

import os.path

from my_project_conf import fabconf

#  Do not edit
fabconf['FAB_CONFIG_PATH'] = os.path.dirname(__file__)

# Username for connecting to EC2 instances - Do not edit unless you have a reason to
fabconf['SERVER_USERNAME'] = "ubuntu"

# Full local path for .ssh
fabconf['SSH_PATH'] = "~/.ssh"

# Don't edit. Full path of the ssh key you use to connect to EC2 instances
fabconf['SSH_PRIVATE_KEY_PATH'] = '%s/%s' % (fabconf['SSH_PATH'], fabconf['EC2_KEY_NAME'])

# Where to install apps
fabconf['APPS_DIR'] = "/home/%s/webapps" % fabconf['SERVER_USERNAME']

# Where you want your project installed: /APPS_DIR/PROJECT_NAME
fabconf['PROJECT_PATH'] = "%s/%s" % (fabconf['APPS_DIR'], fabconf['PROJECT_NAME'])

# Change this if manage.py is not in PROJECT_PATH
fabconf['MANAGEPY_PATH'] = fabconf['PROJECT_PATH']

# Path for virtualenvs
fabconf['VIRTUALENV_DIR'] = "/home/%s/.virtualenvs" % fabconf['SERVER_USERNAME']

# Git username for the server
fabconf['GIT_USERNAME'] = "EC2"

# Name of the private key file used for github deployments
fabconf['BITBUCKET_DEPLOY_KEY_NAME'] = "id_dsa"

# Don't edit. Local path for deployment key you use for github
fabconf['BITBUCKET_DEPLOY_KEY_PATH'] = "%s/%s" % (fabconf['SSH_PATH'], fabconf['BITBUCKET_DEPLOY_KEY_NAME'])

# Creates the ssh location of your bitbucket repo from the above details
fabconf['BITBUCKET_REPO'] = "ssh://git@bitbucket.org/%s/%s.git" % (fabconf['BITBUCKET_USERNAME'], fabconf['BITBUCKET_REPO_NAME'])

# Virtualenv activate command
fabconf['ACTIVATE'] = "source /home/%s/.virtualenvs/%s/bin/activate" % (fabconf['SERVER_USERNAME'], fabconf['PROJECT_NAME'])
