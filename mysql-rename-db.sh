#!/bin/bash
# mysql-rename-db.sh
#
# Renames a database to a new name.


info () { [ "$verbose" = "yes" ] && echo "$*" ; }
error () { echo "Error: $*" ; exit 1 ; }

usage () {
    echo "Usage: $(basename $0) <db_name> [new_db_name]"
    echo "    db_name:      Name of the db to be renamed."
    echo "    new_db_name:  New name for the database."
    echo "         (default: <db_name>_MOVED)"
    echo ""
    echo "    -h,--help     Show this message and exit."
    echo "    -v,--verbose  Increase verbosity level."
    echo ""
}


parse_opts () {
    tempopt=$(getopt --name $(basename $0) -o u,h,v -l usage,help,verbose -- "$@")
    # Finish if received some unknown option.
    if [ $? != 0 ] ; then usage && exit 1 ; fi

    eval set -- "$tempopt"

    # Default values for command-line options.
    verbose='no'

    # Parse named options.
    while true ; do
        case "$1" in
            -u|--usage|-h|--help) usage && exit ;;
	    -v|--verbose) verbose=yes ; shift ;;
            --) shift ; break ;;
            *) echo "Internal error!" >&2 ; exit 1 ;;
        esac
    done

    # Parse arguments.
    if [ $# -lt 1 ] ; then usage && exit 1 ; fi
    if [ $# -gt 2 ] ; then usage && exit 1 ; fi
    db_old=$1
    if [ $# -eq 2 ] ; then
	db_new=$2
    else
	db_new="${db_old}_MOVED"
    fi
}




######################################################################


parse_opts "$@"

db_new="${db_old}_MOVED"


# Check if database exists.
mysql ${db_old} -e '' > /dev/null 2>&1
if [ $? -ne 0 ] ; then
	error "${db_old} database not found."
fi
mysql ${db_new} -e '' > /dev/null 2>&1
if [ $? -eq 0 ] ; then
	error "${db_new} database already exists."
fi

# Get list of tables.
tables=$(mysql -N -e "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE table_schema='${db_old}'")


info "CREATE DATABASE ${db_new}"
mysql -N -e "CREATE DATABASE ${db_new}"
if [ $? -ne 0 ] ; then
	error "can't create ${db_new}"
fi

for table in $tables ; do
	info "Moving ${db_old}.$table"
	mysql -N -e "RENAME TABLE ${db_old}.${table} TO ${db_new}.${table} ;"
done

missed_tables=$(mysql ${db_old} -e 'show tables ;')
if [ -n "${missed_tables}" ] ; then
	error "${db_old} database not empty."
else
	info "DROP DATABASE ${db_old}"
	#mysql -N -e "DROP DATABASE ${db_old}"
fi

