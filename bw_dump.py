#!/usr/bin/env python
import json
import os.path
import subprocess
import time
import argparse
from write_to_file import WriteToFile, EncryptAndWriteToFile

COMMON_CLI_PARAMS: list = ['--raw']


def bw_exec(cmd, ret_encoding='UTF-8', env_vars=None) -> str:
    cmd.extend(COMMON_CLI_PARAMS)

    cli_env_vars = os.environ

    if env_vars is not None:
        cli_env_vars.update(env_vars)
    print(f"Executing CLI :: {' '.join(cmd)}")
    command_out = subprocess.run(cmd, capture_output=True, check=False, encoding=ret_encoding, env=cli_env_vars)

    if len(command_out.stdout) > 0:
        return command_out.stdout

    if len(command_out.stderr) > 0:
        return command_out.stderr
    return ""


if __name__ == '__main__':

    bw_current_status = json.loads(bw_exec(["bw", "status"]))

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", '--directory', help="Bitwarden Dump Location", default=f'bitwarden_dump_{int(time.time())}')
    parser.add_argument("-g", '--gpg-fpr', help="gpg-key-id for file encryption")
    args, unknown = parser.parse_known_args()

    if bw_current_status['status'] != 'unlocked':
        raise Exception('Unable to unlock the vault')

    if args.gpg_fpr is None:
        file_writer = WriteToFile()
    else:
        file_writer = EncryptAndWriteToFile(args.gpg_fpr)

    # Syn latest version
    bw_sync_status = bw_exec(["bw", "sync"])
    # if bw_sync_status != 'Syncing complete.':
    #    raise Exception('Failed to sync vault :: ' + bw_sync_status)

    # Fetch Organization Details
    bw_organizations = json.loads((bw_exec(['bw', 'list', 'organizations'])))
    bw_items = json.loads((bw_exec(['bw', 'list', 'items'])))
    bw_folders = json.loads((bw_exec(['bw', 'list', 'folders'])))
    bw_collections = json.loads((bw_exec(['bw', 'list', 'collections'])))

    items_lists_based_on_organization: dict = {}
    attachments_list: list = []
    for bw_organization in bw_organizations:
        items_lists_based_on_organization[bw_organization['id']] = {'collections': [], 'folders': [], 'items': []}
    items_lists_based_on_organization[bw_current_status['userId']] = {'collections': [], 'folders': [], 'items': []}

    while len(bw_items) > 0:
        bw_item = bw_items.pop()
        if bw_item['organizationId'] is not None:
            items_lists_based_on_organization[bw_item['organizationId']]['items'].append(bw_item)
            org_or_user_id = bw_item['organizationId']
        else:
            items_lists_based_on_organization[bw_current_status['userId']]['items'].append(bw_item)
            org_or_user_id = bw_current_status['userId']

        if 'attachments' not in bw_item:
            continue
        for attachment in bw_item['attachments']:
            print(f"Downloading Attachment \n {attachment}")
            path = os.path.join(os.path.abspath(args.directory), org_or_user_id, 'attachments', bw_item['id'], attachment['id'])
            if not os.path.exists(path):
                os.makedirs(path)

            attachment_cmd_out = bw_exec(['bw', 'get', 'attachment', '--itemid', bw_item['id'], attachment['id']], ret_encoding='')

            file_writer.write(attachment_cmd_out, os.path.join(path, attachment['fileName']))

    while len(bw_folders) > 0:
        bw_folder = bw_folders.pop()
        items_lists_based_on_organization[bw_current_status['userId']]['folders'].append(bw_folder)

    while len(bw_collections) > 0:
        bw_collection = bw_collections.pop()
        items_lists_based_on_organization[bw_collection['organizationId']]['collections'].append(bw_collection)

    for export_dict, org_details in items_lists_based_on_organization.items():
        print(export_dict)
        path = os.path.join(os.path.abspath(args.directory), export_dict)
        if not os.path.exists(path):
            os.makedirs(path)
        file_writer.write(json.dumps(items_lists_based_on_organization[export_dict], indent=4), os.path.join(path, 'export.json'))
