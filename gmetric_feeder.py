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
import commands



class Gmetric (object):
    """Base class for retrieving data and putting it into gmetric.
    """

    def __init__ (self):
        self.data = self.get_status()


    # Overwrite this method for derived classes.
    def get_status (self):
        """Retrieves data from some source. Returns a dictionary with keys
        and values to be stored with gmetric.
        """
        return {}

    
    def gmetric_formated (self, key, rrd_type, name=None, unit=None):
        """Returns values formatted for gmetric (Ganglia).
    
        args:    (data, name, key, rrd_type, unit) or 
                (data, name, key, rrd_type)
        """
        
        template = 'gmetric -n "%s" -v "%s" -t "%s"'

        if name is None:
            name = key.lower()
        gmetric_cmd = template % ( name, self.data[key], rrd_type )
    
        if not unit is None:
            gmetric_cmd = ' '.join( (gmetric_cmd, '-u "%s"' % unit) )
    
        return gmetric_cmd
    
    
    def __run__ (self, cmd):
        """Saves data into Gmetric.
        """
        return commands.getstatusoutput(cmd)


    def __repr__(self):
        lines = [ self.gmetric_formated(*param)  for param in self.params ]
        return '\n'.join(lines)


    def save (self):
        for param in self.params:
            cmd = self.gmetric_formated(*param)
            self.__run__(cmd)






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
        import MySQLdb
        
        # Create a connection object and create a cursor
        conn = MySQLdb.Connect(db="mysql", read_default_file="~/.my.cnf")
        cursor = conn.cursor()
        sql = "SHOW STATUS ;"
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
    
        return dict(results)



def main():
    """Execute the program.
    """
    
    # Parse command-line.
    usage = """usage: %prog [options]"""
    parser = OptionParser(usage=usage)
    
    parser.add_option("-n", "--dry-run", action="store_true",
                      help="do nothing; just show", dest="dry_run")
    parser.add_option("-a", "--apache", action="store_true",
                      help="Apache mod_status")
    parser.add_option("-m", "--mysql", action="store_true",
                      help="Mysql SHOW STATUS")
    
    opts, ___ = parser.parse_args()
    
    
    if opts.apache:
        if opts.dry_run:
            print Apache()
        else:
            Apache().save()

    if opts.mysql:
        if opts.dry_run:
            print Mysql()
        else:
            Mysql().save()



if __name__ == "__main__":
    main()
