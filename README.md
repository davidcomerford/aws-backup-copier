# aws-backup-jobs-copier

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
usage: job-copier.py [-h] [--arn ARN]

Copy AWS Backup recovery points between vaults.

optional arguments:
  -h, --help  show this help message and exit
  --arn ARN   ARN of role for copy jobs (default: arn:aws:iam::1234:role/service-role/AWSBackupDefaultServiceRole)
````