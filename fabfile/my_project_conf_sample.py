__author__ = 'Chuck Martin'

# Config params you want to make sure do not end up in a public repo.
# Copy this file to my_project_conf.py
# It will be imported into project_conf.py

fabconf = {}

# Project name
fabconf['PROJECT_NAME'] = u'{{ project_name }}'  # Works as a Django startproject template

# Name of the private key file you use to connect to EC2 instances
fabconf['EC2_KEY_NAME'] = "my_ssh_key.pem"

# App domains: space delimited
fabconf['DOMAINS'] = "example.com www.example.com"

# Email for the server admin
fabconf['ADMIN_EMAIL'] = "admin@example.com"

# Path to the repo of the application you want to install
fabconf['BITBUCKET_USERNAME'] = ''
fabconf['BITBUCKET_REPO_NAME'] = ''

# Name tag for your server instance on EC2
fabconf['INSTANCE_NAME_TAG'] = "MyInstance"

# EC2 key. http://bit.ly/j5ImEZ
fabconf['AWS_ACCESS_KEY'] = ''

# EC2 secret. http://bit.ly/j5ImEZ
fabconf['AWS_SECRET_KEY'] = ''

#EC2 region. http://amzn.to/12jBkm7
ec2_region = 'ap-southeast-2'

# AMI name. http://bit.ly/liLKxj
ec2_amis = ['ami-51821b6b']

# Name of the keypair you use in EC2. http://bit.ly/ldw0HZ
ec2_keypair = 'insert_keypair_name'

# Name of the security group. http://bit.ly/kl0Jyn
ec2_secgroups = ['MySecurityGroup']

# API Name of instance type. http://bit.ly/mkWvpn
ec2_instancetype = 't1.micro'

# Existing instances - add the public dns of your instances here when you have spawned them
fabconf['EC2_INSTANCES'] = [""]