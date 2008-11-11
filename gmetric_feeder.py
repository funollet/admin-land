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
import copy


def oneliner(cmd, stdin=None):
    """Execs the string in a shell. Returns cmd output.

    @cmd:       string with the command to be executed
    @stdin:     (optional) string writen to the command's standard input
    """
    pipe = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ret = pipe.communicate(stdin)
    
    if pipe.returncode == 0:
        return ret[0]
    else:
        return None




class GmetricSaver(object):
    
    def __init__(self):
        
        # Multicast port to send/receive on.
        self.port = None
        self.template = ['gmetric','--name %s', '--value %s', '--type %s']
    
    
    def __call__(self):
        """Overwrite __call__ to make this class work as a singleton."""
        return self
    
    
    def template_builder(self, unit=False):
        tmpl = copy.copy(self.template)
        if self.port:
            tmpl.insert(1, '--port %s' % self.port)
        
        if unit:
            tmpl += ['--unit %s']

        return ' '.join(tmpl)


    def show (self, params, data):
        pass

# Kind of singleton.
GmetricSaver = GmetricSaver()


class Gmetric (object):
    """Base class for retrieving data and putting it into gmetric.
    """

    def __init__ (self):
        """Initialize the object.
        
        Must define a self.params dict of keys we want into gmetric, and
        a self.data dict.
        """
        
        self.gs = GmetricSaver()


    def __gmetric_formated__ (self, key, rrd_type, name=None, unit=None):
        """Returns values formatted for gmetric (Ganglia).
        """
        
        if name is None:
            name = key.lower()
        
        # name:            gmetric --name
        # self.data[key]:  gmetric --value
        # rrd_type:        gmetric --type
        # unit:            gmetric --unit
    
        if not unit:
            gmetric_cmd = self.gs.template_builder() % ( name, self.data[key], rrd_type )
        else:
            gmetric_cmd = self.gs.template_builder(unit) % ( name, self.data[key], rrd_type, unit )

        return gmetric_cmd
    
    
    def __get_commands__(self):
        """Build a list of commands that should be executed to put data
        into Ganglia."""
        if self.data:
            return [ self.__gmetric_formated__(*param)  for param in self.params]
        else:
            return ''
        
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
            
        self.data = self.get_status()
        super( Apache, self ).__init__()

        
    def get_status (self):
        """Retrieve data from Apache's mod_status.
        """
        try:
            sock = urllib.urlopen( self.url )
        except IOError:
            # Unable to open a socket. Don't save any value, but keep running.
            return None
        page = sock.read()
        sock.close()
    
        status = [line.split(': ') for line in page.splitlines()]
        try:
            return dict(status)
        except ValueError:
            # The /server-status page can not be retrieved.
            return None





class Mysql (Gmetric):
    """Gets status from Mysql and digest it for gmetric.

    Put authentication data on '~/.my.cnf', please.
    """
    
    def __init__ (self):
        """Initializes values.
        """
        
        # params format:
        # (self.data[key], gmetric-type, gmetric-name, gmetric-unit)
        self.params = (
            ('Questions', 'uint16', 'mysql_queries', 'queries' ),
            ('Threads_connected', 'uint16', 'mysql_threads_conn', 'threads'),
            ('Com_select', 'uint16', 'mysql_select_queries', 'queries/sec'),
            ('Table_locks_waited', 'float', 'mysql_table_locks_waited',
                'locks/sec'),
            ('Slow_queries', 'float', 'mysql_slow_queries', 'queries/sec' ),
        )
                   
        self.data = self.get_status()
        super( Mysql, self ).__init__()



    def get_status (self):
        """Retrieve data from Mysql's 'SHOW STATUS'.
        """
        
        output = oneliner('mysql', 'SHOW STATUS')
        if not output:
            return None
        
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



class Vsftpd(Gmetric):
    """Gets status from Vsftpd processes and digest it for gmetric.

    Set 'setproctitle_enable=YES' on your vsftpd.conf to show connection 
    status per-process.
    """
    
    def __init__ (self):
        """Initializes values.
        """
        
        self.params = (
            ('vsftpd_clients', 'uint16', 'vsftpd_clients' ),
            ('vsftpd_data_conn_retr', 'uint16', 'vsftpd_data_conn_retr' ),
            ('vsftpd_data_conn_idle', 'uint16', 'vsftpd_data_conn_idle' ),
            ('vsftpd_data_conn_other', 'uint16', 'vsftpd_data_conn_other' ),
        )
        
        self.data = self.get_status()
        super(Vsftpd, self ).__init__()



    def get_status (self):
        """Retrieve data from Vsftpd.
        """
        
        output = oneliner('ps -u ftp -o cmd')
        logging.debug(output)
        if not output:
            return None
        
        # Parse output into a dictionary.
        result = {}
        # Remove starting 'vsftpd: '. Resulting format: [ <ip>, <data> ]
        conns = [ line.split(': ')[1:] for line in output.split('\n') ]
        conns = conns[1:-1]    # Remove header and empty line.
        
        ips = [ ip  for ip, data in conns if data == 'connected' ]
        result['vsftpd_clients'] = len(set(ips))
        data_retr = [ data  for ___, data in conns if data.startswith('RETR') ]
        result['vsftpd_data_conn_retr'] = len(data_retr)
        data_idle = [ data  for ___, data in conns if data.startswith('IDLE') ]
        result['vsftpd_data_conn_idle'] = len(data_idle)
        data_other = [ data  for ___, data in conns if not data.startswith(('connected', 'RETR', 'IDLE')) ]
        result['vsftpd_data_conn_other'] = len(data_other)
        
        return result




class Exim (Gmetric):
    """Parses data about Exim usage.
    """
    
    def __init__ (self):
        """Initializes values.

        %params: fields from Exim we want to get.
        """
        
        self.params = (
            ( 'exim_incoming_queue', 'int16', 'exim_incoming_queue', 'messages'),
            ( 'exim_outgoing_queue', 'int16', 'exim_outgoing_queue', 'messages'),

        )

        self.data = self.get_status()
        super( Exim, self ).__init__()

        
    def get_status (self):
        result = {}
        try:
            # Remove the trailing '\n.
            result['exim_incoming_queue'] = oneliner('/usr/sbin/exim -bpc')[:-1]
            result['exim_outgoing_queue'] = oneliner('/usr/sbin/exim -bpc -DOUTGOING')[:-1]
        except OSError:
            return None

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
    parser.add_option("-p", "--port", action="store",
                      help="multicast port for Ganglia")
    parser.add_option("-a", "--apache", action="store_true",
                      help="Apache mod_status")
    parser.add_option("-m", "--mysql", action="store_true",
                      help="Mysql SHOW STATUS")
    parser.add_option("-f", "--vsftpd", action="store_true",
                      help="vsftpd status")
    parser.add_option("-e", "--exim", action="store_true",
                      help="Exim status")

    
    opts, ___ = parser.parse_args()
    
    # Set debug level.
    if opts.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    gs = GmetricSaver()
    if opts.port:
        gs.port = opts.port
    
    # TODO: add --url for Apache().
    if opts.apache:
        Apache().save(opts.dry_run)
    if opts.mysql:
        Mysql().save(opts.dry_run)
    if opts.vsftpd:
        Vsftpd().save(opts.dry_run)
    if opts.exim:
        Exim().save(opts.dry_run)


if __name__ == "__main__":
    main()
