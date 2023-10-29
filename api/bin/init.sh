#!/bin/sh

sqlite3 ./var/primary/fuse/userData.db < ./share/projectDatabase.sql
sqlite3 ./var/primary/fuse/userData.db < ./share/project2Database.sql
