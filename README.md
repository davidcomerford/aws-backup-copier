# AWS Backup Copier

Copy recovery points between AWS Backup vaults

## Requirements

- boto3 `pip install boto3`
- rich `pip install rich`

## Installation

````bash
python -m venv venv
source venv/bin/activate
pip install rich boto3
chmod +x job-copier.py
````

## Usage

````none
usage: backup_copier.py [-h] --source SOURCE --destination DESTINATION [--arn ARN] [--all]

Copy AWS Backup recovery points between vaults.

options:
  -h, --help            show this help message and exit
  --source SOURCE       Name of the vault to copy from (example: SourceVault)
  --destination DESTINATION
                        ARN of the destination vault (example: arn:aws:backup:eu-west-1:271595718296:backup-vault:NewProdVault)
  --arn ARN             ARN of role for copy jobs (default: arn:aws:iam::1234:role/service-role/AWSBackupDefaultServiceRole)
  --all                 Copy all recovery points. Does NOT check copy job history to remove already completed copies.
````