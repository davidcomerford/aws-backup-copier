#!/usr/bin/python3

from glob import glob
from os import times
from tokenize import String
#from colorama import Style
from rich import print
from rich import box
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.text import Text
from time import sleep
from random import random
from datetime import datetime
import boto3
from rich import print
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
import argparse

# Variables - Tunable
max_conncurrent_copy_jobs = 2 # max 5
table_update_frequency = 5  # in seconds


# Variables - Don't Change
source_vault_arn = "arn:aws:backup:eu-west-1:271595718296:backup-vault:pRoD"
source_vault_name = "pRoD"
destination_vault_arn = "arn:aws:backup:eu-west-1:271595718296:backup-vault:uat-RDS-Vault"
recovery_point_count = 0
recovery_point_count_queded = 0
copy_jobs_completed = 0
jobs_in_flight = []
finisihed = False

# Boto3 clients
backup_client = boto3.client('backup')
sts_client = boto3.client('sts')

# Rich widgets
console = Console()
layout = Layout()

def make_layout() -> Layout:
    """Create the layout"""
    layout.split_column(
        Layout(name="title"),
        Layout(name="upper"),
        Layout(name="lower")
    )
    layout["title"].size = 3
    layout["upper"].size = 8
    layout["upper"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    return layout


def make_header_panel() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")  # , ratio=1)
    grid.add_column(justify="center")
    grid.add_column(justify="right")
    grid.add_row(
        "Role: " + get_account_role(),
        "Acount: " + get_account_id(),
        datetime.now().ctime().replace(":", "[blink]:[/]"),
    )

    header_panel = Panel(
        grid,
        box=box.ROUNDED,
        padding=(0, 0),
        title="",
        # border_style="bright_blue",
        style="white on blue",
    )
    return header_panel


def make_source_vault_panel() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_row("ARN: " + source_vault_arn)
    grid.add_row("Recovery Points: " + str(recovery_point_count))
    grid.add_row("Queued for copy: " + str(recovery_point_count_queded))
    grid.add_row(progress)

    message_panel = Panel(
        grid,
        box=box.ROUNDED,
        padding=(1, 2),
        title="[b red]Source Vault",
        border_style="bright_blue",
    )
    return message_panel


def make_destination_vault_panel() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_row("ARN: " + destination_vault_arn)
    grid.add_row("Job role: " + copy_role_arn)
    grid.add_row("Max concurrent copy jobs: " + str(max_conncurrent_copy_jobs))
    grid.add_row("Completed copy jobs: " + str(copy_jobs_completed))

    message_panel = Panel(
        grid,
        box=box.ROUNDED,
        padding=(1, 2),
        title="[b green]Destination Vault",
        border_style="bright_blue",
    )
    return message_panel

def make_jobs_placeholder() -> Text:
    """This is just to fill the void until the jobs table is created"""
    text = Text(
        "Loading...",
        justify="center"
        )
    return text

def update_jobs_table(source_point_arn: str, jobs_in_flight: dict) -> None:
    # Make a new table
    table = Table(expand=True, header_style="dim", box=box.SIMPLE)
    table.add_column("Polled At", justify="left")
    table.add_column("Recovery Point", justify="left", no_wrap=True)
    table.add_column("Copy Job ID", justify="left", no_wrap=True)
    table.add_column("Backup Size (Bytes)", justify="right")
    table.add_column("Creation Date", justify="left", style="green")
    table.add_column("Completion Date", justify="left", style="green")
    table.add_column("State", justify="left", style="green")

    # Make a timestamp
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    # Populate the table
    for job in jobs_in_flight:
        table.add_row(
            timestamp,
            str(job['SourceRecoveryPointArn']),
            str(job['CopyJobId']),
            str(job['BackupSizeInBytes']),
            str(job.get('CreationDate').strftime("%d-%m-%Y %H:%M:%S")),
            str(job.get('CompletionDate', "-")),
            str(job.get('State')))
    
    return table


def make_progress_bar(total_steps) -> Progress:
    progress= Progress(
        "{task.description}",
        SpinnerColumn(),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )
    progress.add_task("Progress", total=total_steps)
    return progress


def update_progress() -> None:
    global copy_jobs_completed
    copy_jobs_completed += 1
    progress.advance(0, 1)


def get_account_id():
    return sts_client.get_caller_identity()["Account"]


def get_account_role():
    return str(sts_client.get_caller_identity()["Arn"])


def get_backup_role_for_copy() -> String:
    role = "arn:aws:iam::" + get_account_id() + ":role/service-role/AWSBackupDefaultServiceRole"
    return role


def test_vault_access(vault) -> bool:
    try:
        response= backup_client.describe_backup_vault(
            BackupVaultName=vault
        )
        return True
    except:
        return False


def get_vault_details(vault) -> dict:
    try:
        response= backup_client.describe_backup_vault(
            BackupVaultName=vault
        )
        return response
    except Exception as e:
        console.log(f'fuck: {e}')
        exit


def get_recovery_points():
    try:
        paginator= backup_client.get_paginator(
            'list_recovery_points_by_backup_vault')
        response_iterator= paginator.paginate(
            BackupVaultName=source_vault_name
        )
        return [e['RecoveryPoints'] for e in response_iterator][0]
    except Exception as e:
        console.log(f'fuck: {e}')
        exit


def get_recovery_points_count(vault) -> int:
    global recovery_point_count
    details= get_vault_details(vault)
    recovery_point_count= details['NumberOfRecoveryPoints']
    return recovery_point_count


def get_copy_jobs_at_start():
    response= backup_client.list_copy_jobs(
        ByState='COMPLETED'
    )
    copy_jobs= response['CopyJobs']
    return copy_jobs


def get_copy_job_details(copy_job_id):
    response= backup_client.describe_copy_job(
        CopyJobId=copy_job_id
    )
    copy_jobs= response['CopyJob']
    return copy_jobs


def get_points_left_to_copy_count() -> dict:
    global recovery_point_count_queded
    recovery_point_count_queded= len(source_points)
    return recovery_point_count_queded


def remove_recovery_point(recovery_point_arn):
    """ Remove point from list in source vault """
    global recovery_point_count_queded

    for index in range(len(source_points)):
        if source_points[index]['RecoveryPointArn'] == recovery_point_arn:
            del source_points[index]
            recovery_point_count_queded= recovery_point_count_queded - 1
            layout["left"].update(make_source_vault_panel())
            break


def prune_already_copied_points():
    """Removes points that have already been copied to destination vault"""
    for copy_job in copy_jobs:

        # copy_job_destination_point_arn = copy_job['DestinationRecoveryPointArn']
        copy_job_source_point_arn= copy_job['SourceRecoveryPointArn']
        copy_job_id= copy_job['CopyJobId']

        # Find any copy jobs that match points in destination vault so they don't have to be copied again
        if copy_job['DestinationBackupVaultArn'] == destination_vault_arn:
            console.log(
                f'Removing recovery point {copy_job_source_point_arn} from queue because found copy job ID {copy_job_id} to same destination')
            source_point_to_remove= copy_job['SourceRecoveryPointArn']

            # Remove point from list in source vault
            for index in range(len(source_points)):
                if source_points[index]['RecoveryPointArn'] == source_point_to_remove:
                    del source_points[index]
                    break

#
# Execution Start
#

parser = argparse.ArgumentParser(description='Copy AWS Backup recovery points between vaults.')
parser.add_argument(
    '--arn',
    required=False,
    help='ARN of role for copy jobs (default: arn:aws:iam::1234:role/service-role/AWSBackupDefaultServiceRole)'
    )

args = parser.parse_args()
print(args.arn)
print("working")
sleep(3)

# Sanity tests
if test_vault_access(source_vault_name):
    console.log(f'Verified access to vault: {source_vault_name}')
else:
    console.log(f"Could not access vault: {source_vault_name}. Exiting")
    exit()

# Get the ARNs and counts
source_vault= get_vault_details('pRoD')
source_points= get_recovery_points()
copy_jobs= get_copy_jobs_at_start()
console.log(f'Found {len(copy_jobs)} copy jobs')

prune_already_copied_points()
get_recovery_points_count(source_vault_name)
get_points_left_to_copy_count()
progress= make_progress_bar(recovery_point_count_queded)

copy_role_arn = get_backup_role_for_copy()

# Layout
layout= make_layout()
layout["title"].update(make_header_panel())
layout["left"].update(make_source_vault_panel())
layout["right"].update(make_destination_vault_panel())
layout["lower"].update(make_jobs_placeholder())


# Live updates
with Live(layout, refresh_per_second=1, screen=True):
    sleep(0.5)
    while not finisihed:

        for index in range(len(source_points)):
            if len(jobs_in_flight) < max_conncurrent_copy_jobs:

                current_source_point_arn= source_points[0]['RecoveryPointArn']

                # Create copy job
#                copy_job_id= "ABF93B0E-1622-4FCA-B087-26C1AF4B2EA2" # mock
                copy_job_response = backup_client.start_copy_job(
                    RecoveryPointArn=current_source_point_arn,
                    SourceBackupVaultName=source_vault_name,
                    DestinationBackupVaultArn=destination_vault_arn,
                    IamRoleArn=get_backup_role_for_copy()
                )
                copy_job_id = copy_job_response['CopyJobId']

                # Get the job details
                job_details= get_copy_job_details(copy_job_id)

                # Add the source point arn to the job_details dict to display in the table
                job_details['RecoveryPointArn']= current_source_point_arn

                # Add the job details to the jobs_in_flight dict
                jobs_in_flight.append(job_details)

                # Remove recovery point from the queue
                remove_recovery_point(source_points[0]['RecoveryPointArn'])

                # Update the renderables
                layout["lower"].update(update_jobs_table(current_source_point_arn, jobs_in_flight))
                layout["left"].update(make_source_vault_panel())
                layout["right"].update(make_destination_vault_panel())

            else:
                while len(jobs_in_flight) == max_conncurrent_copy_jobs:
                    for job in jobs_in_flight:

                        copy_job_id= job['CopyJobId']
                        # Get the job details
                        job_details= get_copy_job_details(copy_job_id)

                        # Update the renderables
                        layout["lower"].update(update_jobs_table(current_source_point_arn, jobs_in_flight))
                        layout["left"].update(make_source_vault_panel())
                        layout["right"].update(make_destination_vault_panel())

                        # Check if it's done
                        state= get_copy_job_details(copy_job_id)['State']
                        if state == 'COMPLETED':

                            update_progress()
                            jobs_in_flight.remove(job)
                    sleep(table_update_frequency)
        update_progress()

        # while True:
        #     sleep(0.1)
        #     update_jobs_table('fdsfd',{'CopyJobId':'f','BackupSizeInBytes':'3','CreationDate':datetime.now(),'CompletionDate':datetime.now(),'State':'yeeting'})
        sleep(10)
        finisihed= True
console.log(f'Copied {copy_jobs_completed} recovery points')
console.log('Done')
