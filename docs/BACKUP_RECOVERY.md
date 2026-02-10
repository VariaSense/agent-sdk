# Backup and Recovery

The CLI provides lightweight backup/restore commands for the storage and control-plane databases.

## Create a Backup
```bash
agent-sdk backup create --output-dir backups --label "pre-upgrade"
```

## List Backups
```bash
agent-sdk backup list
```

## Restore
```bash
agent-sdk backup restore backup_1234abcd
```

## Dry Run
```bash
agent-sdk backup restore backup_1234abcd --dry-run
```

## Notes
- SQLite backends copy the database files listed in `AGENT_SDK_DB_PATH` and
  `AGENT_SDK_CONTROL_PLANE_DB_PATH`.
- Postgres backends rely on `pg_dump` for backups and `psql` for restores.
- The control plane stores backup metadata in the `backups` table.
