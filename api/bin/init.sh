#!/bin/sh

sqlite3 ./var/projectDatabase.db < ./share/projectDatabase.sql
sqlite3 ./var/project2Database.db < ./share/project2Database.sql
