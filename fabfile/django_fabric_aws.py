"""
--------------------------------------------------------------------------------------
django_fabric_aws.py
--------------------------------------------------------------------------------------
A set of fabric commands to manage a Django deployment on AWS

author : Chuck Martin, https://github.com/cwurld/Django-Fabric-AWS
credit : Derived from:
            1) Ashok Fernandez (github.com/ashokfernandez/)
            2) https://github.com/gcollazo/Fabulous
date   : May 24, 2014

Changes from Ashok Fernandez: brought contents of tasks.py into this file. Tasks.py represented each task as
    a list of dictionaries. This file would convert each dict into a Fabric command. It is not clear this level
    of indirection is useful. This modification creates each Fabric command directly.

    The motivation for this change was to make it easier to use the Fabric with command. I think the code is also
    more readable.

Commands include:
    - fab spawn instance
        - Spawns a new EC2 instance (as defined in project_conf.py) and returns it's public dns
          This takes around 8 minutes to complete.

    - fab update_packages
        - Updates the python packages on the server to match those found in requirements/common.txt and
          requirements/prod.txt

    - fab deploy
        - Pulls the latest commit from the master branch on the server, collects the static files, syncs the db and
          restarts the server

    - fab reload_gunicorn
        - Pushes the gunicorn startup script to the servers and restarts the gunicorn process, use this if you
          have made changes to templates/start_gunicorn.bash

    - fab reload_nginx
        - Pushes the nginx config files to the servers and restarts the nginx, use this if you
          have made changes to templates/nginx-app-proxy or templates/nginx.conf

    - fab reload_supervisor
        - Pushes the supervisor config files to the servers and restarts the supervisor, use this if you
          have made changes to templates/supervisord-init or templates/supervisord.conf

    - fab manage:command="management command"
        - Runs a python manage.py command on the server. To run this command we need to specify an argument, eg for
          syncdb type the command -> fab manage:command="syncdb --no-input"
"""
import os
import json
import StringIO

from fabric.api import run, sudo, env, put, settings, cd
from fabric.colors import green as _green, yellow as _yellow
from project_conf import fabconf, ec2_region, ec2_keypair, ec2_secgroups, ec2_instancetype, ec2_amis
import boto
import boto.ec2
import time

from gen_secret import gen_secret
from write_secrets import write_secrets

# AWS user credentials
env.user = fabconf['SERVER_USERNAME']
env.key_filename = fabconf['SSH_PRIVATE_KEY_PATH']

# List of EC2 instances to work on
env.hosts = fabconf['EC2_INSTANCES']
         
# ------------------------------------------------------------------------------------------------------------------
# MAIN FABRIC TASKS - Type fab <function_name> in the command line to execute any one of these
# ------------------------------------------------------------------------------------------------------------------


def spawn():
    env.hosts = []


def instance():
    """
    Creates an EC2 instance from an Ubuntu AMI and configures it as a Django server
    with nginx + gunicorn
    """
    # Record the starting time and print a starting message
    start_time = time.time()
    print(_green("Started..."))

    # Use boto to create an EC2 instance
    env.host_string = _create_ec2_instance()
    print(_green("Waiting 30 seconds for server to boot..."))
    time.sleep(30)

    # First command as regular user
    run('whoami')

    # Sudo apt-get update
    print(_yellow("Updating apt-get"))
    sudo("apt-get update -qq")

    # List of APT packages to install
    print(_yellow("Installing apt-get packages"))
    _apt(["libpq-dev", "nginx", "memcached", "git", "python-setuptools", "python-dev", "build-essential",
          "python-pip", "libmemcached-dev"])

    # List of pypi packages to install
    print(_yellow("Installing pip packages"))
    _pip(["virtualenv", "virtualenvwrapper", "supervisor"])

    # Add AWS credentials to the a config file so that boto can access S3
    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/boto.cfg",
                   "destination": "/home/%(SERVER_USERNAME)s/boto.cfg"})
    sudo(_r("mv /home/%(SERVER_USERNAME)s/boto.cfg /etc/boto.cfg"))

    # virtualenvwrapper
    print(_yellow("Configuring virtualenvwrapper"))
    sudo(_r("mkdir %(VIRTUALENV_DIR)s"))
    sudo(_r("chown -R %(SERVER_USERNAME)s: %(VIRTUALENV_DIR)s"))
    run(_r("echo 'export WORKON_HOME=%(VIRTUALENV_DIR)s' >> /home/%(SERVER_USERNAME)s/.profile"))
    run(_r("echo 'source /usr/local/bin/virtualenvwrapper.sh' >> /home/%(SERVER_USERNAME)s/.profile"))
    run(_r("source /home/%(SERVER_USERNAME)s/.profile"))

    # webapps alias
    print(_yellow("Creating webapps alias"))
    run(_r("""echo "alias webapps='cd %(APPS_DIR)s'" >> /home/%(SERVER_USERNAME)s/.profile"""))

    # webapps dir
    print(_yellow("Creating webapps directory"))
    sudo(_r("mkdir %(APPS_DIR)s"))
    sudo(_r("chown -R %(SERVER_USERNAME)s: %(APPS_DIR)s"))

    # git setup
    print(_yellow("Configuring git"))
    run(_r("git config --global user.name '%(GIT_USERNAME)s'"))
    run(_r("git config --global user.email '%(ADMIN_EMAIL)s'"))
    put(_r("%(BITBUCKET_DEPLOY_KEY_PATH)s"), _r("/home/%(SERVER_USERNAME)s/.ssh/%(BITBUCKET_DEPLOY_KEY_NAME)s"))
    run(_r("chmod 600 /home/%(SERVER_USERNAME)s/.ssh/%(BITBUCKET_DEPLOY_KEY_NAME)s"))
    run(_r("echo 'IdentityFile /home/%(SERVER_USERNAME)s/.ssh/%(BITBUCKET_DEPLOY_KEY_NAME)s' >> "
           "/home/%(SERVER_USERNAME)s/.ssh/config"))
    run(_r("ssh-keyscan bitbucket.org >> /home/%(SERVER_USERNAME)s/.ssh/known_hosts"))

    # Create virtualenv
    print(_yellow("Creating virtualenv"))
    run(_r("mkvirtualenv --no-site-packages %(PROJECT_NAME)s"))

    # Install django in virtualenv
    print(_yellow("Installing django"))
    _virtualenv("pip install Django")

    # Install psycopg2 drivers for Postgres
    print(_yellow("Installing psycopg2"))
    _virtualenv("pip install psycopg2")

    # Install gunicorn in virtualenv
    print(_yellow("Installing gunicorn"))
    _virtualenv("pip install gunicorn")

    # Install django cache
    _virtualenv("pip install pylibmc")
    _virtualenv("pip install django-elasticache")
    _virtualenv("pip install boto")
    _virtualenv("pip install django-storages")

    # Clone the git repo
    run(_r("git clone %(BITBUCKET_REPO)s %(PROJECT_PATH)s"))
    put(_r("%(FAB_CONFIG_PATH)s/templates/gunicorn.conf.py"), _r("%(PROJECT_PATH)s/gunicorn.conf.py"))

    # Create run and log dirs for the gunicorn socket and logs
    run(_r("mkdir %(PROJECT_PATH)s/logs"))

    # Add gunicorn startup script to project folder
    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/start_gunicorn.bash",
                   "destination": "%(PROJECT_PATH)s/start_gunicorn.bash"})
    sudo(_r("chmod +x %(PROJECT_PATH)s/start_gunicorn.bash"))

    # Install the requirements from the pip requirements files
    _virtualenv("pip install -r %(PROJECT_PATH)s/requirements/production.txt --upgrade")

    # nginx
    print(_yellow("Configuring nginx"))
    put(_r("%(FAB_CONFIG_PATH)s/templates/nginx.conf"), _r("/home/%(SERVER_USERNAME)s/nginx.conf"))
    sudo("mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.old")
    sudo(_r("mv /home/%(SERVER_USERNAME)s/nginx.conf /etc/nginx/nginx.conf"))
    sudo("chown root:root /etc/nginx/nginx.conf")
    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/nginx-app-proxy",
                   "destination": "/home/%(SERVER_USERNAME)s/%(PROJECT_NAME)s"})
    sudo("rm -rf /etc/nginx/sites-enabled/default")
    sudo(_r("mv /home/%(SERVER_USERNAME)s/%(PROJECT_NAME)s /etc/nginx/sites-available/%(PROJECT_NAME)s"))
    sudo(_r("ln -s /etc/nginx/sites-available/%(PROJECT_NAME)s /etc/nginx/sites-enabled/%(PROJECT_NAME)s"))
    sudo(_r("chown root:root /etc/nginx/sites-available/%(PROJECT_NAME)s"))

    # Setup secrets for Django
    update_secrets(new_secret=True)

    print(_yellow("Restarting nginx"))
    sudo("/etc/init.d/nginx restart")

    # Run collectstatic and syncdb
    _virtualenv("python %(MANAGEPY_PATH)s/manage.py collectstatic -v 0 --noinput")
    _virtualenv("python %(MANAGEPY_PATH)s/manage.py syncdb")

    # Setup supervisor
    print(_yellow("Configuring supervisor"))
    run(_r("echo_supervisord_conf > /home/%(SERVER_USERNAME)s/supervisord.conf"))
    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/supervisord.conf",
                   "destination": "/home/%(SERVER_USERNAME)s/my.supervisord.conf"})
    run(_r("cat /home/%(SERVER_USERNAME)s/my.supervisord.conf >> /home/%(SERVER_USERNAME)s/supervisord.conf"))
    run(_r("rm /home/%(SERVER_USERNAME)s/my.supervisord.conf"))
    sudo(_r("mv /home/%(SERVER_USERNAME)s/supervisord.conf /etc/supervisord.conf"))
    sudo("supervisord")
    put(_r("%(FAB_CONFIG_PATH)s/templates/supervisord-init"), _r("/home/%(SERVER_USERNAME)s/supervisord-init"))
    sudo(_r("mv /home/%(SERVER_USERNAME)s/supervisord-init /etc/init.d/supervisord"))
    sudo("chmod +x /etc/init.d/supervisord")
    sudo("update-rc.d supervisord defaults")

    # Print out the final runtime and the public dns of the new instance
    end_time = time.time()
    print(_green("Runtime: %f minutes" % ((end_time - start_time) / 60)))
    print(_green("\nPLEASE ADD ADDRESS THIS TO YOUR ")),
    print(_yellow("project_conf.py")),
    print(_green(" FILE UNDER ")),
    print(_yellow("fabconf['EC2_INSTANCES'] : ")),
    print(_green(env.host_string))


def deploy():
    """
    Pulls the latest commit from bitbucket, rsyncs the database, collects the static files and restarts the
    server.
    """
    start = check_hosts()
    print(_yellow("Updating server to latest commit in the bitbucket repo..."))

    # Pull the latest version from the bitbucket repo
    run(_r("cd %(PROJECT_PATH)s && git pull"))

    # Update the database
    _virtualenv("python %(MANAGEPY_PATH)s/manage.py collectstatic -v 0 --noinput")
    _virtualenv("python %(MANAGEPY_PATH)s/manage.py syncdb")

    # Restart gunicorn to update the site
    sudo(_r("supervisorctl restart %(PROJECT_NAME)s"))

    time_diff = time.time() - start
    print(_yellow("Finished updating the server in %.2fs" % time_diff))


def update_packages():
    """
    Updates the python packages on the server as defined in requirements/common.txt and 
    requirements/prod.txt
    """
    start = check_hosts()
    print(_yellow("Updating server packages with pip..."))

    # Updates the python packages
    _virtualenv("pip install -r %(PROJECT_PATH)s/requirements/common.txt --upgrade")
    _virtualenv("pip install -r %(PROJECT_PATH)s/requirements/prod.txt --upgrade")

    time_diff = time.time() - start
    print(_yellow("Finished updating python packages in %.2fs" % time_diff))


def reload_nginx():
    """
    Reloads the nginx config files and restarts nginx
    """
    start = check_hosts()
    print(_yellow("Reloading the nginx config files..."))

    # Stop old nginx process
    sudo("service nginx stop")

    # Load the nginx config files
    print(_yellow("Configuring nginx"))
    put(_r("%(FAB_CONFIG_PATH)s/templates/nginx.conf"), _r("/home/%(SERVER_USERNAME)s/nginx.conf"))
    sudo("mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.old")
    sudo(_r("mv /home/%(SERVER_USERNAME)s/nginx.conf /etc/nginx/nginx.conf"))
    sudo("chown root:root /etc/nginx/nginx.conf")

    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/nginx-app-proxy",
                   "destination": "/home/%(SERVER_USERNAME)s/%(PROJECT_NAME)s"})
    sudo("rm -rf /etc/nginx/sites-enabled/default")
    sudo(_r("mv /home/%(SERVER_USERNAME)s/%(PROJECT_NAME)s /etc/nginx/sites-available/%(PROJECT_NAME)s"))
    sudo(_r("chown root:root /etc/nginx/sites-available/%(PROJECT_NAME)s"))

    print(_yellow("Restarting nginx"))
    sudo("/etc/init.d/nginx restart")

    time_diff = time.time() - start
    print(_yellow("Finished reloading nginx in %.2fs" % time_diff))


def reload_supervisor():
    """
    Reloads the supervisor config files and restarts supervisord
    """
    start = check_hosts()
    print(_yellow("Reloading the supervisor config files..."))

    # Stop old supervisor process
    sudo("supervisorctl stop all")
    sudo("killall supervisord")

    # Setup supervisor
    print(_yellow("Configuring supervisor"))
    run(_r("echo_supervisord_conf > /home/%(SERVER_USERNAME)s/supervisord.conf"))
    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/supervisord.conf",
                   "destination": "/home/%(SERVER_USERNAME)s/my.supervisord.conf"})

    run(_r("cat /home/{SERVER_USERNAME:s}/my.supervisord.conf >> /home/{SERVER_USERNAME:s}/supervisord.conf"))
    run(_r("rm /home/{SERVER_USERNAME:s}/my.supervisord.conf"))
    sudo(_r("mv /home/{SERVER_USERNAME:s}/supervisord.conf /etc/supervisord.conf"))
    sudo("supervisord")
    put(_r("{FAB_CONFIG_PATH:s}/templates/supervisord-init"), _r("/home/{SERVER_USERNAME:s}/supervisord-init"))
    sudo(_r("mv /home/{SERVER_USERNAME:s}/supervisord-init /etc/init.d/supervisord"))
    sudo("chmod +x /etc/init.d/supervisord")
    sudo("update-rc.d supervisord defaults")

    # Restart supervisor
    sudo("supervisorctl start all")

    # Print the final message and the elapsed time
    print(_yellow("%s in %.2fs" % ("Finished reloading supervisor", time.time() - start)))


def reload_gunicorn():
    """
    Reloads the Gunicorn startup script and restarts gunicorn
    """
    start = check_hosts()
    print(_yellow("Reloading the gunicorn startup script..."))

    # Push the gunicorn startup script to server
    _put_template({"template": "%(FAB_CONFIG_PATH)s/templates/start_gunicorn.bash",
                   "destination": "%(PROJECT_PATH)s/start_gunicorn.bash"})
    sudo(_r("chmod +x %(PROJECT_PATH)s/start_gunicorn.bash"))

    # Restart gunicorn to update the site
    sudo(_r("supervisorctl restart %(PROJECT_NAME)s"))

    time_diff = time.time() - start
    print(_yellow("Finished reloading the gunicorn startup script in %.2fs" % time_diff))


def update_secrets(new_secret=False):
    secrets_file = open(fabconf['SECRETS_PATH'], 'rb')
    new_secrets = json.load(secrets_file)
    secrets_file.close()

    if not new_secret:
        # Keeps remote secret
        remote_file_path = fabconf['SETTINGSDIR'] + '/secrets.json'
        remote_file = StringIO.StringIO()
        junk = get(remote_file_path, local_path=remote_file)
        remote_secrets = json.loads(remote_file.getvalue())
        remote_file.close()
        new_secrets['SECRET_KEY'] = remote_secrets['SECRET_KEY']
    else:
        new_secrets['SECRET_KEY'] = gen_secret()

    temp_filename = write_secrets(new_secrets)
    put(temp_filename, _r('%(SETTINGSDIR)s/secrets.json'))
    os.remove(temp_filename)
    print(_yellow("Writing secrets"))


def manage(command):
    """
    Runs a python manage.py command on the server
    """
    
    # Get the instances to run commands on
    env.hosts = fabconf['EC2_INSTANCES']

    # Run the management command inside the virtualenv
    _virtualenv("python %(MANAGEPY_PATH)s/manage.py " + command)


# ------------------------------------------------------------------------------------------------------------------
# SUPPORT FUNCTIONS
# ------------------------------------------------------------------------------------------------------------------
def check_hosts():
    # Get the hosts and record the start time
    env.hosts = fabconf['EC2_INSTANCES']
    start = time.time()

    # Check if any hosts exist
    if not env.hosts:
        raise Exception("There are no EC2 instances defined in project_conf.py, "
                        "please add some instances and try again "
                        "There are EC2 instances defined in project_conf.py, please add some instances and try again "
                        "or run 'fab spawn_instance' to create an instance")
    return start


def _create_ec2_instance():
    """
    Creates EC2 Instance
    """
    print(_yellow("Creating instance"))
    conn = boto.ec2.connect_to_region(ec2_region, aws_access_key_id=fabconf['AWS_ACCESS_KEY'],
                                      aws_secret_access_key=fabconf['AWS_SECRET_KEY'])

    image = conn.get_all_images(ec2_amis)

    reservation = image[0].run(1, 1, ec2_keypair, ec2_secgroups,
                               instance_type=ec2_instancetype)

    this_instance = reservation.instances[0]
    conn.create_tags([this_instance.id], {"Name": fabconf['INSTANCE_NAME_TAG']})
    
    while this_instance.state == u'pending':
        print(_yellow("Instance state: %s" % this_instance.state))
        time.sleep(10)
        this_instance.update()

    print(_green("Instance state: %s" % this_instance.state))
    print(_green("Public dns: %s" % this_instance.public_dns_name))
    
    return this_instance.public_dns_name


def _virtualenv(params):
    """
    Allows running commands on the server
    with an active virtualenv
    """
    with cd(fabconf['APPS_DIR']):
        _virtualenv_command(_render(params))


def _apt(params):
    """
    Runs apt-get install commands
    """
    for pkg in params:
        sudo("apt-get install -qq %s" % pkg)


def _pip(params):
    """
    Runs pip install commands
    """
    for pkg in params:
        sudo("pip install %s" % pkg)


def _put(params):
    """
    Moves a file from local computer to server
    """
    put(_render(params['file']), _render(params['destination']))


def _put_template(params):
    """
    Same as _put() but it loads a file and does variable replacement
    """
    f = open(_render(params['template']), 'r')
    template = f.read()

    run(_write_to(_render(template), _render(params['destination'])))


def _render(template, context=fabconf):
    """
    Does variable replacement
    """
    return template % context


def _r(template):
    """
    Does variable replacement.
    """
    return template % fabconf


def _write_to(string, the_path):
    """
    Writes a string to a file on the server
    """
    return "echo '" + string + "' > " + the_path


def _append_to(string, the_path):
    """
    Appends to a file on the server
    """
    return "echo '" + string + "' >> " + the_path


def _virtualenv_command(command):
    """
    Activates virtualenv and runs command
    """
    with cd(fabconf['APPS_DIR']):
        sudo(fabconf['ACTIVATE'] + ' && ' + command, user=fabconf['SERVER_USERNAME'])
