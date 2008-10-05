#!/usr/bin/env python
# gmetric_feeder.py
# -*- coding: utf-8 -*-
#
# Jordi Funollet <jordi.f@ati.es>

"""Gets params from serveral sources and digests it.
Finally, invokes 'gmetric' to introduce the data into Ganglia.
"""


import urllib
from optparse import OptionParser
import subprocess
import logging


def oneliner(cmd, stdin=''):
    """Execs the string in a shell. Returns cmd output.

    @cmd:       string with the command to be executed
    @stdin:     (optional) string writen to the command's standard input
    """
    if stdin:
        pipe = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        pipe.stdin.write(stdin)
    else:
        pipe = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    return pipe.communicate()[0]





class Gmetric (object):
    """Base class for retrieving data and putting it into gmetric.
    """

    def __init__ (self):
        """Initialize the object."""
        self.data = self.get_status()

    # Overwrite this method for derived classes.
    def get_status (self):
        """Retrieves data from some source. Returns a dictionary with keys
        and values to be stored with gmetric.
        """
        return {}

    
    def __gmetric_formated__ (self, key, rrd_type, name=None, unit=None):
        """Returns values formatted for gmetric (Ganglia).
    
        args:    (data, name, key, rrd_type, unit) or 
                (data, name, key, rrd_type)
        """
        
        template = 'gmetric -n "%s" -v "%s" -t %s'

        if name is None:
            name = key.lower()
        gmetric_cmd = template % ( name, self.data[key], rrd_type )
    
        if not unit is None:
            gmetric_cmd = ' '.join( (gmetric_cmd, '-u "%s"' % unit) )
    
        return gmetric_cmd
    
    
    def __get_commands__(self):
        """Build a list of commands that should be executed to put data
        into Ganglia."""
        return [ self.__gmetric_formated__(*param)  for param in self.params ]
        
    def __repr__(self):
        """Printable representation."""
        return '\n'.join(self.__get_commands__())

    def save (self, dry_run=False):
        """Put data into Ganglia."""
        
        for cmd in self.__get_commands__():
            logging.debug(cmd)
            if not dry_run:
                oneliner(cmd)






class Apache (Gmetric):
    """Gets data from Apache mod_status and digest it for gmetric.

    Put something like this on your Apache configuration.

    ExtendedStatus On
    <Location /server-status>
        SetHandler server-status
        Order deny,allow
        Deny from all
        Allow from 127.0.0.1
    </Location>
    """
    
    def __init__ (self, url=None):
        """Initializes values.

        %params: fields in mod_status we want to get.
        %url: (optional)
        """
        
        self.params = (
            ( 'BytesPerSec', 'int16', 'apache_bytes', 'Bytes/sec'),
            ( 'ReqPerSec', 'float', 'apache_hits', 'Requests/sec'),
            ( 'BusyWorkers', 'int16', 'apache_workers_busy', 'Processes'),
            ( 'IdleWorkers', 'int16', 'apache_workers_idle', 'Processes'),
        )

        if not url:
            self.url = 'http://localhost/server-status/?auto'
        else:
            self.url = url

        super( Apache, self ).__init__()

        
    def get_status (self):
        """Retrieve data from Apache's mod_status.
        """
        
        sock = urllib.urlopen( self.url )
        page = sock.read()
        sock.close()
    
        status = [line.split(': ') for line in page.splitlines()]
        return dict(status)





class Mysql (Gmetric):
    """Gets status from Mysql and digest it for gmetric.

    Put authentication data on '~/.my.cnf', please.
    """
    
    def __init__ (self):
        """Initializes values.

        %params: fields in 'show status' we want to get.
        """
        
        self.params = (
            ('Questions', 'uint16', 'mysql_queries', 'queries' ),
            ('Threads_connected', 'uint16', 'mysql_threads_conn', 'threads'),
            ('Com_select', 'uint16', 'mysql_select_queries', 'queries/sec'),
            ('Table_locks_waited', 'float', 'mysql_table_locks_waited',
                'locks/sec'),
            ('Slow_queries', 'float', 'mysql_slow_queries', 'queries/sec' ),
        )
                   
        super( Mysql, self ).__init__()



    def get_status (self):
        """Retrieve data from Mysql's 'SHOW STATUS'.
        """
        
        output = oneliner('mysql', 'SHOW STATUS')
        # Parse output into a dictionary.
        result = {}
        for line in output.split('\n'):
            try:
                key, value = line.split()
            except ValueError:
                key = line
                value = ''
            result[key] = value
        
        return result



def main():
    """Command line interface.
    """
    
    # Parse command-line.
    usage = """usage: %prog [options]"""
    parser = OptionParser(usage=usage)
    
    parser.add_option("-v", "--verbose", action="store_true",
                      help="show more information", dest="verbose")
    parser.add_option("-n", "--dry-run", action="store_true",
                      help="do nothing; just show", dest="dry_run")
    parser.add_option("-a", "--apache", action="store_true",
                      help="Apache mod_status")
    parser.add_option("-m", "--mysql", action="store_true",
                      help="Mysql SHOW STATUS")
    
    opts, ___ = parser.parse_args()
    
    # Set debug level.
    if opts.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if opts.apache:
        Apache().save(opts.dry_run)

    if opts.mysql:
        Mysql().save(opts.dry_run)


if __name__ == "__main__":
    main()
