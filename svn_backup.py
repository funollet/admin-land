#!/usr/bin/env python
# -*- coding:utf-8 -*-
# svn_backup.py
"""
Helps managing incremental SVN backups. Removes old backups overlapped by
newer ones and creates a directory structure for storing the backups.
"""

import glob, os, time
from optparse import OptionParser
import logging

# Customize as needed.
DEFAULT_DUMP_DIR = '/home/backups/svn/'


###### REFACTORING #######

#class SvnDmpFile:
    #def __init__ (self, fname):
        #self.fname = fname
        #self.repository = os.path.basename(self.fname).split('.')[0]
        #self.rev_low, self.rev_high = self.__get_revisions__()
    
    
    #def __get_revisions__ (self):
        #"""Extracts revision numbers from a svn-backup-dumps generated
        #filename.
        #Returs: (minor_rev, major_rev).
        #"""
        #dotsplitted = self.fname.split('.')
        #revisions = dotsplitted[ dotsplitted.index('svndmp') - 1 ]
        #return tuple( revisions.split('-') )
    
    #def __eq__ (self, another):
        #if self.fname == another.fnames:
            #return True
        #else:
            #return False

## Do we need a SvnDmpRepository class?
## But that's the same than having SvnDmp, ain't that?

#class SvnDmpDir:
    #def __init__ (self, basepath):
        #self.basepath = os.path.normpath(os.path.expanduser(basepath))
        #self.dumps = []  # list of SvnDmpFile
        
    #def scan_directory (self):
        #for fname in os.listdir(self.basepath):
            #new_dump = SvnDmpFile(fname)
            #if new_dump.fname != :
                #self.dumps.append (new_dump)
        
    #def get_repository_names(self):
        #"""All repository names, without repetitions."""
        #return None
    
#############################


class SvnDmp:
    """Represents a SVN incremental dumpfile. Can identify overlapped files.
    """
    
    def __init__(self, fnames):
        """
        fnames can be:
        * List of filenames.
        * One filename.
        * A pattern including some filenames in JUST ONE repository.
        """
        if type(fnames) == str:
            self.fnames = self.__expand_fnames__(fnames)
        else:
            self.fnames = fnames
            self.fnames.sort()
        
    
    def __get_revisions_in_name__ (self, filename):
        """Extracts revision numbers from a svn-backup-dumps generated filename.
        Returs: (minor_rev, major_rev).
        """
        dotsplitted = filename.split('.')
        revisions = dotsplitted[ dotsplitted.index('svndmp') - 1 ]
        return tuple( revisions.split('-') )


    def get_revisions (self):
        """All revision tuples (minor_rev, major_rev) for every filename in
        this object.
        """
        return [ self.__get_revisions_in_name__(f)  for f in self.fnames ]
    
    
    def get_overlapped_revisions (self):
        """Revision tuples (minor_rev, major_rev) of filenames having his
        revisions contained in another filename.
        """
        revisions = self.get_revisions()
        minors = set( [r[0] for r in revisions] )
    
        result = []
        for minor in minors:
            majors = [int(r[1]) for r in revisions if r[0]==minor ]
            max_majors = max(majors)
            overlaped = [ '%06d' % maj  for maj in majors if maj != max_majors ]
            result += [(minor, o) for o in overlaped]
    
        result.sort()
        return result


    
    def get_overlapped_files (self): 
        """Every filename having his revisions contained in another filename.
        """
        overlapped_files = []
        for revs in self.get_overlapped_revisions():
            for fname in self.fnames:
                if '%s-%s' % revs in fname:
                    overlapped_files.append (fname)
                    break
        
        return overlapped_files


    def __expand_fnames__ (self, fname_pattern):
        """Given a file name pattern returns all files being versions of
        the same backup. Shell expansion will be done.
        """
        
        if '*' in fname_pattern:
            f_split = glob.glob(fname_pattern)[0].split('.')
        else:
            f_split = fname_pattern.split('.')
        
        f_split[ f_split.index('svndmp')-1 ] = '*'
        f_split = f_split[:f_split.index('svndmp')]
        fnames = glob.glob('.'.join(f_split))
        fnames.sort()
        return fnames
        
        




def find_base_files (search_dir):
    """Scans all base svn-dump files in a directory (those with -r 0). Returns
    one of them for every svn-dumps (can be more than one).
    """
    
    expanded_dir = os.path.normpath(os.path.expanduser(search_dir))
    full_pattern = os.path.join(expanded_dir, '*.000000-*')
    base_files = glob.glob(full_pattern)
    base_files.sort()
    
    # None or only one filename.
    if len(base_files) <= 1:
        return base_files
    
    filtered = []
    filtered.append (base_files[0])
    for next in base_files[1:]:
        # Another dump from the same repository? Don't append.
        if next.split('.')[0] != filtered[-1].split('.')[0]:
            filtered.append(next)
    
    return filtered



################################################################################

def prepare_full (dump_root_dir):
    """Create directory infrastructure so next SVN dump will be full."""
    
    new_dir = time.strftime ('%Y-%m-%d')
    
    os.chdir (dump_root_dir)
    os.mkdir (new_dir, 0700)
    if os.path.islink('latest'):
        os.remove('latest')
    if not os.path.exists('latest'):
        os.symlink (new_dir, 'latest')
    else:
        raise Exception, "Unable to link '%s' as 'latest'." % new_dir



def cleanup_action (dump_dir, dry_run=False):
    """Removes files overlapped by other files.
    """

    base_files =  find_base_files (dump_dir)
    overlapped = [SvnDmp(fname).get_overlapped_files()  for fname in base_files]

    for fname in overlapped:
        if dry_run:
            logging.debug('remove %s' % fname)
        else:
            os.remove(fname)



def main():
    """Main program."""
    
    usage = u"usage: %prog [options] dumpdir"
    parser = OptionParser( usage=usage )
    parser.add_option( "-c", "--cleanup",
        action="store_true", dest="cleanup", default=False,
        help=u"echoes files overwritten by later dumps." )
    parser.add_option( "-p", "--prepare-full",
        action="store_true", dest="prepare_full", default=False,
        help=u'creates a directory structure for doing a full dump' )
    parser.add_option("-n", "--dry-run", action="store_true",
                      help="do nothing; just show", dest="dry_run")
    (options, args) = parser.parse_args()

    # Set debug level.
    if options.dry_run:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    if options.cleanup:
        if len(args) < 1:
            cleanup_action (os.path.join(DEFAULT_DUMP_DIR, 'latest'))
        else:
            cleanup_action (args[0])

    if options.prepare_full:
        prepare_full (DEFAULT_DUMP_DIR)

if __name__ == "__main__":
    main()
