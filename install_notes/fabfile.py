# -*- coding: utf-8 -*-
# fabfile.py
"""Deploys software too hard to manage via Puppet.
"""

from fabric.api import run, env, cd, sudo, settings, puts
from fabric.contrib.files import exists, append, sed
from fabric import colors
  

env.user = 'root'


def __apt_do(command, pkgs):
    """Run 'aptitude %(command)' without questions. Preserves old configs.
    
    command:    aptitude command to be run.
    pkgs:       packages to install/remove (string).

Example: __apt_do('install', 'nginx php-cgi')
    """

    aptitude = '''DEBIAN_FRONTEND=noninteractive /usr/bin/aptitude \
    -q  -y -o 'DPkg::Options::=--force-confold' %s %s'''

    #with settings(hide('stdout')):
    cmdline = aptitude % (command, pkgs)
    run(' '.join(cmdline.split()))




def __generate_password (length=8):
    """Returns a random password of the given 'length' (default=8).
    """

    import random

    ascii_letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    digits = '0123456789'
    allchars = ascii_letters + digits
    password = ''
    generator = random.Random()
    for ___ in range(0, length):
        password += generator.choice(allchars)

    return password



def __apt_do(command, pkgs):
    """Run 'aptitude %(command)' without questions. Preserves old configs.
    
    command:    aptitude command to be run.
    pkgs:       packages to install/remove (string).

Example: __apt_do('install', 'nginx php-cgi')
    """

    aptitude = '''DEBIAN_FRONTEND=noninteractive /usr/bin/aptitude \
    -q  -y -o 'DPkg::Options::=--force-confold' %s %s'''

    #with settings(hide('stdout')):
    cmdline = aptitude % (command, pkgs)
    run(' '.join(cmdline.split()))

    

def __git_get(url, username='nobody'):
    """Runs 'git clone' (if no local repos. is found) or 'git pull'.

    url:        URL of the Git remote repository.
    """

    # Extract from URL the name of the directory to be created.
    # TODO: parse git-SSH urls, too.
    dest_dir = url.split('/')[-1].split('.git')[0]

    if not exists("%s/.git/" % dest_dir):
        run("git clone -q %s" % url)
        run("chown -R %s: %s" % (username, dest_dir) )
    else:
        with cd(dest_dir):
            sudo("git pull", user=username)



def __wget(url):
    """Download a file to /tmp.
    """
    cmd = "wget -q --no-check-certificate -P /tmp/ -nc %s" % url
    sudo(cmd, user='nobody')


def __untar(name):
    """Extracts a tarfile pre-cached in /tmp. Assings ownership to 'nobody'.

    Tarfile must be in /tmp and end in '.tar.gz'.
    """

    run("tar -xzf /tmp/%s.tar.gz" % name)
    run("chown -R nobody: %s" % name)
    # Sanitize dummy-created tar files.
    run("chmod -R o-w %s" % name)


#def __get_host_release(valid_names=None):
#    """Retrieves OS release; optionaly, checks it's one of "valid_names".
#    
#    valid_names: names of acceptable release names (list)
#    """
#
#    # Install lsb-release, if not available.
#    with settings(warn_only=True):
#        result = run('test -f /usr/bin/lsb_release')
#    if result.failed:
#        __apt_do("install", 'lsb-release')
#        
#    codename = run('lsb_release --short --codename')
#    if valid_names:
#        if codename not in valid_names:
#            abort("OS release not supported: %s" % codename)
#    return codename
    

############################################################


def puppet():
    """Install puppet in a new host.
    """
    __apt_do('install', 'rails puppet git-core libsqlite3-ruby')
    sed('/etc/default/puppet', 'START=yes', 'START=no')
    run('/etc/init.d/puppet stop')


def puppetmaster(sysadmin='nobody'):
    """Install puppetmasterd.
    """

    __apt_do("install", "puppetmaster rails sqlite3")
    # If storeconfigs use sqlite3, this needs write access to the directory
    # containing the DB file.
    run("sudo chown puppet: /var/lib/puppet/state/")

    # One user edit files.
    run("chown -R %s: /etc/puppet/" % sysadmin)



# Needed for searchsounds2.
def pylucene(release='2.4.1-2'):
    """Install pylucene.
    
    release: (not tested). Default: 2.4.1-2.
    """

    

    makefile_patch = '''
--- Makefile.orig       2010-03-23 16:20:57.000000000 +0100
+++ Makefile    2010-03-22 19:05:43.000000000 +0100
@@ -80,5 +80,5 @@
-#PREFIX_PYTHON=/usr
-#ANT=ant
-#PYTHON=\$(PREFIX_PYTHON)/bin/python
-#JCC=\$(PYTHON) -m jcc --shared
-#NUM_FILES=2
+PREFIX_PYTHON=/usr
+ANT=ant
+PYTHON=\$(PREFIX_PYTHON)/bin/python
+JCC=\$(PYTHON) -m jcc
+NUM_FILES=2
'''

    pkg_build = 'python-dev sun-java6-jdk  ant build-essential subversion'

    # Run-time dependencies.
    __apt_do('install', 'sun-java6-jre')
    # Compile-time dependencies.
    __apt_do('install', pkg_build)
    # ant changed this to gij; fix it or pylucene fails to build.
    run("update-alternatives --set java /usr/lib/jvm/java-6-sun/jre/bin/java")
    run("update-alternatives --set javac /usr/lib/jvm/java-6-sun/bin/javac")


    src_tar = "pylucene-%s-src.tar.gz" % release
    src_dir = "pylucene-%s" % release
    url = "http://apache.rediris.es/lucene/pylucene/%s" % src_tar

    with cd('/usr/local/src'):
        # download
        __wget(url)
        run("mv /tmp/%s /tmp/%s.tar.gz" % (src_tar, src_dir))
        __untar(src_dir)

        # make_jcc
        with cd('%s/jcc' % src_dir):
            run("JCC_JDK='/usr/lib/jvm/java-6-sun' python setup.py build")
            run("JCC_JDK='/usr/lib/jvm/java-6-sun' python setup.py install")

        # make pylucene
        with cd(src_dir):
            append(makefile_patch, '/tmp/Makefile.patch')
            run('patch -b Makefile /tmp/Makefile.patch')
            run('make')
            run('make install')


    # cleanup
    run('rm /tmp/%s.tar.gz' % src_dir)
    __apt_do('remove', pkg_build)




def zeromq():
    """Install/upgrade 0mq under /usr/local/.
    """

    src_dir = "/usr/local/src" 
    release_old, release = "zeromq-2.1.7", "zeromq-2.1.7"
    url = "http://download.zeromq.org/%s.tar.gz" % release

    # Compile time dependencies.
    pkg_build = "build-essential pkg-config libtool autoconf automake" \
        + " uuid-dev libglib2.0-dev"

    if exists('/usr/local/src/%s' % release):
        puts(colors.green("zeromq: already installed"))
        return
    
    __apt_do('install', pkg_build)
    # Run time dependencies.
    __apt_do('install', "libuuid1")

    __wget(url)

    # Cleanup before upgrading.
    with cd(src_dir): 
        with settings(warn_only=True):
            # Remove last deployment.
            run("test -d %s && mv %s /tmp" % (release_old, release_old))

    with cd(src_dir): 
        __untar(release)
        
        with cd(release):
            sudo("./configure", user='nobody')
            sudo("make", user='nobody')
            run("make install")

    run("ldconfig")

    # Cleanup.
    __apt_do('remove', pkg_build)



def openvmtools ():
    """Build package open-vm-modules on Debian Squeeze.
    """

    pkg_build = """module-assistant build-essential linux-headers-2.6-amd64
        open-vm-source"""
    pkg_runtime = """open-vm-tools"""

    __apt_do("install", pkg_build)
    __apt_do("install", pkg_runtime)
    run("module-assistant build open-vm-source")
    __apt_do("purge", pkg_build)
    print """
Now get the package and add it to our local APT repository. Should look
like:
    
    /usr/src/open-vm-modules-2.6.32-5-amd64_8.4.2-261024-1+2.6.32-31_amd64.deb
    """
    # reprepro includedeb squeeze \
    #   open-vm-modules-2.6.32-5-amd64_8.4.2-261024-1+2.6.32-31_amd64.deb



def supercollider():
    """Deploy supercollider 3.4 from SVN.
    """

    src_base_dir = "/usr/local/src"
    src_dir = "${src_base_dir}/supercollider-branch-3.4"
    url_release = "https://supercollider.svn.sourceforge.net/svnroot/supercollider/branches/3.4/"

    # Build-time dependencies.
    pkg_build = """subversion scons pkg-config libavahi-client-dev libicu-dev
        libjack-dev  libreadline5-dev  libsndfile-dev  libasound2-dev"""

    # Run-time dependencies.
    pkg_runtime = """libsndfile1 fftw3 libjack0 libasound2 libavahi-client3
        libreadline5 libicu38"""

    __apt_do("install", pkg_build)
    __apt_do("install", pkg_runtime)


    with cd(src_base_dir):
        # Checkout source.
        run("svn co %s supercollider-branch-3.4" % url_release)
    with cd(src_dir):
        # scons install
        run("scons SCEL=no")
        # Remove installed binaries:
        #with cd('common/'):
        #    run("scons -c install")
    
    __apt_do("remove", pkg_build)

