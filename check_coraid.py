#!/usr/bin/env python
# check_coraid.py
"""
Nagios plugin, checks status of a Coraid shelf. Runs commands 'show -l'
and 'list -l' and compares output with a previously stored file.

Requirements:
  * Coraid Ethernet Console (cec)
  * 'pexpect' Python module

Before using the plugin for monitoring a Coraid device you must store its
output on a file to compare against. You can do it with the option '--create'.
Do it when the Coraid device is in good status.

Example:

  # check_coraid.py -i eth2 --shelf 0 --create

This plugin must run 'cec' as root and, if there's a timeout, must be able to
kill it. That means you need something like this on your /etc/sudoers file.

  nagios  ALL= NOPASSWD: /usr/local/lib/nagios/plugins/check_coraid.py
  
This is giving full privileges to the script, so please check that no one can
overwrite the Nagios plugin neither the 'cec' binary.

This script is inspired on 'aoe-chk-coraid.sh' by William A. Arlofski
(http://www.revpol.com/coraid_scripts).
"""

# Copyright 2009 Jordi Funollet <jordi.f@ati.es>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


import pexpect
import StringIO
import sys
import os
from optparse import OptionParser
import logging

# Full path of the 'cec' binary.
CEC = '/usr/local/bin/cec'
# How many seconds to wait before killing 'cec'.
CEC_TIMEOUT = 5


def parse_command_line ():
    """Optparse wrapper.
    """

    usage = "usage: %prog <options>"
    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--shelf", action="store", default=0,
                      help="number of the shelf (default: 0)")
    parser.add_option("-i", "--interface", action="store", default='eth0',
                      help="interface to bind (default: eth0)")
    parser.add_option("-b", "--basedir", action="store",
        default='/var/lib/check_coraid',
        help="directory for baseline files (default: /var/lib/check_coraid)")
    parser.add_option("-w", "--show", action="store_true",
                      help="show commands on stdout and exit",)
    parser.add_option("-c", "--create", action="store_true",
                      help="create initial baseline file",)
    parser.add_option("-d", "--debug", action="store_true", default=False,
                      help="show debugging info")

    options, args = parser.parse_args()

    return (options, args)



def nagios_ok(msg):
    """Outputs OK message in Nagios format and exits.
    """
    print "OK: %s" % msg
    sys.exit(0)

def nagios_critical(msg):
    """Outputs CRITICAL message in Nagios format and exits.
    """
    print "CRITICAL: %s" % msg
    sys.exit(2)

def nagios_unknown(msg):
    """Outputs UNKNOWN message in Nagios format and exits.
    """
    print "UNKNOWN: %s" % msg
    sys.exit(3)


def cec_expect(shelf, interface):
    """Runs commands 'show -l' and 'list -l' on a Coraid console.
    
    @shelf: number of the shelf
    @interface: interface to bind
    
    Uses the pexpect module to send commands and retrieve output.
    """
    
    # Using pexpect with the 'cec' client gives a unsorted or noisy
    # output. I add some extra carriage-returns before and after the
    # commands and filter the output to remove lines without information.
    # This workaround seems to be enough.
    
    cec_cmd = "%s -s%s -ee %s" % (CEC, shelf, interface)
    # Run with 'sudo' unless we are root.
    if os.getuid() != 0:
        cec_cmd = "sudo %s" % cec_cmd
        
    logging.debug(cec_cmd)

    # File-like object to write pexpect output.
    output = StringIO.StringIO()

    child = pexpect.spawn(cec_cmd, timeout=CEC_TIMEOUT)
    try:
        child.expect("Escape is Ctrl-e")
        child.sendline("")
        child.sendline("")
        child.sendline("")
        child.expect("SR shelf(.*)>")
        
        child.logfile = output
        
        # Run 'show -l'.
        child.sendline("show -l")
        child.sendline("")
        child.sendline("")
        child.sendline("")
        child.expect("SR shelf(.*)>")
    
        # Run 'list -l'
        child.sendline("")
        child.sendline("")
        child.sendline("")
        child.sendline("list -l")
        child.sendline("")
        child.sendline("")
        child.sendline("")
        child.expect("SR shelf(.*)>")
        
        # Stop capturing output.
        child.logfile = None
        # Disconnect.
        child.send("\r")
        child.send("")
        child.expect(">>>")
        child.send("q\r")
        child.expect(pexpect.EOF)
        child.close()
    except (pexpect.TIMEOUT, pexpect.EOF):
        child.close(force=True)
        
    return cec_normalize(output.getvalue())



def is_informative(line):
    """Returns True if the line contains significative information.
    """
    if line == '' or line.startswith(('SR shelf', 'list -l', 'show -l')):
        return False
    return True
    

def cec_normalize(text):
    """Filter irrelevant lines.
    """
    lines = text.split('\n')
    goodlines = [line for line in lines if is_informative(line)]
    return '\n'.join(goodlines)



def get_baseline(baseline_fname):
    """Returns the contents of a baseline file for use as reference.
    
    @shelf:    number of the shelf.
    @base_dir: directory with the baseline files.
    """
    try:
        baseline_file = open(baseline_fname)
    except IOError:
        nagios_unknown( 
            "cannot open %s. Run the plugin with --create for initialization."
            % baseline_fname)

    baseline = ''.join(baseline_file.readlines())
    # Skip the last '\n' added.
    return baseline[:-1]


def create_baseline(baseline_fname, contents):
    """Create a baseline file to compare with on next runs.
    """
    try:
        baseline_file = open(baseline_fname, 'w')
    except IOError:
        nagios_unknown("cannot open %s" % baseline_fname)

    print >> baseline_file, contents
    baseline_file.close()




def main():
    """Runs unless the file is imported.
    """
    
    # Parse command-line.
    opts, ___ = parse_command_line()
    # Set debug level.
    if opts.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    baseline_fname = os.path.join(opts.base_dir, 
        'shelf%s.baseline' % opts.shelf)
    
    if not os.path.isfile(CEC):
        nagios_unknown("%s not found" % CEC)

    try:
        output = cec_expect(opts.shelf, opts.interface)
    except pexpect.TIMEOUT:
        nagios_critical("AoE shelf%s not responding" % opts.shelf)

    if opts.create:
        create_baseline(baseline_fname, output)
        sys.exit()
    
    if opts.show:
        print output
        sys.exit()
        
    baseline = get_baseline(baseline_fname)
        
    if baseline == output:
        nagios_ok("AoE shelf%s looks as usual" % opts.shelf)
    else:
        nagios_critical("AoE shelf%s has changes" % opts.shelf)


if __name__ == '__main__':
    main()