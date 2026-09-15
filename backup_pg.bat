@echo off
docker run --rm -v jefrey-postgres:/tmp postgres:16 tar czf /tmp/pgbackup.tar.gz -C /var/lib/postgresql/data . 2>nul
docker cp jefrey-postgres:/tmp/pgbackup.tar.gz .\pgbackup.tar.gz
tar xzf pgbackup.tar.gz -C /tmp/pgbackup
echo.
echo "PG backup extracted. Checking for sessions.db..."
if exist /tmp/pgbackup\data\default\base\*.db do (
    echo Found DB files:
    dir /tmp/pgbackup\data\default\base\*.db /b
)
if exist /tmp/pgbackup\sessions.db do (
    echo sessions.db found, size:
    dir /tmp/pgbackup\sessions.db /a
) else (
    echo sessions.db NOT found in PG backup
)