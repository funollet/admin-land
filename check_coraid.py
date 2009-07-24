#!/usr/bin/env python
# check_coraid.py
"""
Nagios plugin, checks status of a Coraid shelf. Runs commands 'show -l'
and 'list -l' and compares output with a previously stored file.

Requirements:
  * Coraid Ethernet Console (cec)
  * 'pexpect' Python module

First usage: run with --show and put the output
on /var/lib/check_coraid/. Example:

  # check_coraid.py -s0 -i eth2 > /var/lib/check_coraid/shelf0.baseline

In order to run as a Nagios plugin you will need to add something
like that to your /etc/sudoers file.

  nagios  ALL= NOPASSWD: /usr/local/bin/cec


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


CEC = '/usr/local/bin/cec'
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
    parser.add_option("-d", "--debug", action="store_true", default=False,
                      help="show debugging info")
    parser.add_option("-q", "--quiet", action="store_true",
                      help="be silent",)

    options, args = parser.parse_args()

    # Check required options.
    #if not args:
    #    parser.error("some arguments are required")

    return (options, args)



def cec_expect(shelf, interface):
    """Runs commands 'show -l' and 'list -l' on a Coraid console.
    
    @shelf: number of the shelf
    @interface: interface to bind
    
    Uses the pexpect module to send commands and retrieve output.
    """
    
    # Using pexpect with the 'cec' client gives a unsorted or noisy
    # output. I added some extra carriage-returns before and after the
    # commands and filter the output to remove lines without information.
    # This workaround seems to be enought.
    
    cec_cmd = "%s -s%s -ee %s" % (CEC, shelf, interface)
    # Run with 'sudo' unless we are root.
    if os.getuid() != 0:
        cec_cmd = "sudo %s" % cec_cmd
        
    logging.debug(cec_cmd)

    # File-like object to write pexpect output.
    output = StringIO.StringIO()

    child = pexpect.spawn(cec_cmd, timeout=CEC_TIMEOUT)
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



def get_baseline(shelf, base_dir):
    """Returns the contents of a baseline file for use as reference.
    
    @shelf:    number of the shelf.
    @base_dir: directory with the baseline files.
    """

    fname = os.path.join(base_dir, 'shelf%s.baseline' % shelf)
    baseline_file = open(fname)
    baseline = ''.join(baseline_file.readlines())
    # Skip the last '\n' added.
    return baseline[:-1]



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

    try:
        output = cec_expect(opts.shelf, opts.interface)
    except pexpect.TIMEOUT:
        if not opts.quiet:
            print "CRITICAL: AoE shelf%s not responding" % opts.shelf
        sys.exit(2)

    
    if opts.show:
        print output
        sys.exit()
        
    try:
        baseline = get_baseline(opts.shelf, opts.basedir)
    except IOError:
        if not opts.quiet:
            print "UNKNOWN: cannot open baseline file for shelf%s" % opts.shelf
        sys.exit(3)
        
    if baseline == output:
        if not opts.quiet:
            print "OK: AoE shelf%s looks as usual" % opts.shelf
        sys.exit(0)
    else:
        if not opts.quiet:
            print "CRITICAL: AoE shelf%s has changes" % opts.shelf
        sys.exit(2)


if __name__ == '__main__':
    main()