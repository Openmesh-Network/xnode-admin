#!/usr/bin/env python

import git
import os
import time
import sys
import psutil
from pathlib import Path
import requests
import json


def parse_args():
    # Simple function to pass in arguments from the command line, argument order is important.
    opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    if len(args) >=3:
        print(sys.argv[1], sys.argv[2], sys.argv[3]) # Git remote
        # input validation for first 3 arguments (eg, int conversion, remote existence / reachability)
    else:
        print("Usage: xnode-rebuilder -[sgd] GIT_LOCAL GIT_REMOTE SEARCH_INTERVAL [USER_KEY] [POWERDNS_URL]")
        print("Git local and remote are required, user key can be SSH or GPG and powerdns is for scaling.")
        print("If using a USER_KEY please specify -s for SSH or -g for gpg.")
        sys.exit(1)

    user_key=None
    key_type=None
    userid=None

    for o in opts:
        if o.startswith("--uuid="):
            userid = o.split('--uuid=')[1]
        if o.startswith("--ssh-dir="):
            user_key = o.split('--ssh-dir=')[1]
            key_type = "ssh"
        elif o.startswith("--gpg-key="):
            user_key = o.split('--gpg-key=')[1]
            key_type = "gpg"
        elif o.startswith("--access-token="):
            user_key = o.split('--access-token=')[1]
            key_type = "access_token"
        
        if o.startswith("-p"): # Find uuid / psk at /proc/cmdline
            with open("/proc/cmdline") as file:
                kvars = file.read().split(" ")
                print(kvars)
                for kvar in kvars:
                    if kvar.startswith("XNODE_UUID="):
                        userid = kvar.split('XNODE_UUID=')[1]
                    if kvar.startswith("XNODE_ACCESS_TOKEN="):
                        user_key = kvar.split('XNODE_ACCESS_TOKEN=')[1]
                        user_key = str(user_key).strip("b''\n'")
                if userid is None or user_key is None:
                    print("Failed to find XNODE_UUID or XNODE_ACCESS_TOKEN in /proc/cmdline")
                    sys.exit(1)
                else:
                    key_type = "access_token"

        if o.startswith("--powerdns="):
            powerdns_url = o.split('=')[1] # Todo

    return args[0], args[1], int(args[2]), user_key, key_type, userid

def main():
    # Program usage: xnode-rebuilder <local path> <git remote repo> <search interval> <optional: GPG Key> <optional: POWERDNS_URL>
    local_repo_path, remote_repo_path, fetch_interval, user_key, key_type, uuid,  = parse_args() # powerdns_url not implemented yet
    print(key_type, user_key, "with uuid ", uuid)

    # Hack to use Xnode Studio API rather than a git remote
    if fetch_interval == 0: # Studio uses a hardcoded interval
        print("Running in Studio mode.")
        if key_type == "access_token":
            # Remote repo is the studio's URL and User key is a preshared secret.
            fetch_config_studio(remote_repo_path, uuid, user_key, local_repo_path)
        else:
            print("Error: Studio mode only supports access token authentication.")
            sys.exit(1)
    else:
        # If there is no git repository at the local path, clone it.
        if not os.path.exists(local_repo_path):
            try:
                git.Repo.clone_from(remote_repo_path, local_repo_path)
            except git.CommandError as e:
                print("Failed to clone repository: ", remote_repo_path, "Error:", e)

        # Initialise interval and git.Repo object
        last_checked = time.time() - fetch_interval # Eligible to search immediately on startup
        repo = git.Repo(local_repo_path)

        # If applicable, add the key to the repo's git config for commit verification
        configure_keys(user_key, key_type, repo)
        git_bin = repo.git

        # Loop forever, pulling changes from git. (Todo: Abstract to function fetch_config_git)
        while True:
            # If the interval has passed since the last check then fetch the latest head.
            if last_checked + fetch_interval < time.time():
                fetch_info = repo.remotes.origin.fetch()
                for fetch in fetch_info:
                    print("Fetched from:", fetch.name)
                    print("Fetched commit:", fetch.commit)

                    # Assuming the branch you care about is 'master'
                    if 'origin/main' in fetch.name:
                        local_commit = repo.heads.main.commit
                        remote_commit = fetch.commit

                        if local_commit.hexsha != remote_commit.hexsha:
                            print("New commits are available on the remote master branch.")
                            # You can list the new commits if necessary

                            # This will print the verification result for each commit
                            try:
                                verification_output = git_bin.verify_commit(remote_commit.hexsha)
                                repo.remotes.origin.pull(remote_commit.hexsha)
                                print("Commit was verified and pulled.", verification_output)
                                rebuild_nixos()

                            except git.GitCommandError as e:
                                print(verification_output)
                                print(e)
                                print("Failed to verify commit:", remote_commit)
                        else:
                            print("Local master is up to date with the remote master.")
                            try:
                                verification_output = git_bin.verify_commit(repo.head.commit.hexsha)
                                print(verification_output)
                            except git.GitCommandError as e:
                                print(e)
                                print("Failed to verify commit:", repo.head.commit)
            last_checked = time.time()

def configure_keys(user_key, use_ssh, repo):
    if user_key is not None:
        if use_ssh:
            try:
                with repo.config_writer() as config:
                    config.set_value("gpg", "format", "ssh")
                    config.set_value('gpg "ssh"',"allowedSignersFile", user_key) # Path to 'keyfile' (similar to an authorized_hosts)
                    config.release()
            except git.GitCommandError:
                print("Failed to set SSH key", git.GitCommandNotFound)
        elif use_ssh is False:
            try:
                with repo.config_writer() as config: # To-do: Implement GPG
                    config.set_value("gpg", "format", "")
                    config.set_value("user","signingKey", user_key) # Hex of gpg public key
                    config.release()
            except git.GitCommandError:
                print("Failed to set SSH key", git.GitCommandNotFound)
        else: # When use_ssh is None
            pass

def rebuild_nixos():
    # To-Do: Return errors to Xnode Studio, possibly by pushing error logs to the git repo.
    # To-Do: Add error handling for a failed nixos rebuild
    exit_code = os.system("/run/current-system/sw/bin/nixos-rebuild switch -I nixos-config=/etc/nixos/configuration.nix")
    print("Rebuild exit code: ", exit_code)
    return exit_code    

def fetch_config_studio(studio_url, xnode_uuid, access_token, state_directory):
    # Talks to the dpl backend to configure the xnode directly.
    hearbeat_interval = 15 # Heartbeat interval in seconds
    last_checked = time.time() - hearbeat_interval # Eligible to search immediately on startup
    cpu_usage_list = []
    mem_usage_list = []

    # Pull changes from Xnode Studio and collecting metrics to send back in heartbeat.
    while True:
        # Collect metrics
        cpu_usage_list.append(psutil.cpu_percent())
        mem_usage_list.append(psutil.virtual_memory().used / (1024 * 1024))

        # If the interval has passed since the last check then fetch from the studio.
        if last_checked + hearbeat_interval < time.time():
            # Calculate metrics (average and maximum)
            avg_cpu_usage, avg_mem_usage, highest_cpu_usage, highest_mem_usage = calculate_metrics(cpu_usage_list, mem_usage_list)

            disk = psutil.disk_usage('/') # Only gets disk usage from root
            headers = {
                'x-parse-session-token': access_token,
            }
            message = {
                "id": str(xnode_uuid),
                "cpuPercent": (avg_cpu_usage),
                "cpuPercentPeek": (highest_cpu_usage),
                "ramMbUsed": (avg_mem_usage),
                "ramMbPeek": (highest_mem_usage),
                "ramMbTotal": (psutil.virtual_memory().total),

                "storageMbUsed":  (disk.used / (1024 * 1024)),
                "storageMbTotal": (disk.total / (1024 * 1024)),
            }
            # Try to send a heartbeat to the studio
            try:
                heartbeat_response = requests.post(studio_url + '/pushXnodeHeartbeat', headers=headers, json=message)
                if not heartbeat_response.ok:
                    print(heartbeat_response.content)   
            except requests.exceptions.RequestException as e:
                print(e)
            # Try to get it's Xnode Configuration
            message = {
                "id": str(xnode_uuid),
            }
            print('Fetching update message at', time.time())
            try:
                config_response = requests.get(studio_url + '/getXnodeServices', headers=headers, json=message)
                if not config_response.ok:
                    print(config_response.content)
                # Process response if one is received
                if config_response.ok:
                    json_path = state_directory+"/latest_config.json"
                    latest_config = config_response.json()
                    config_updated = process_config(latest_config, state_directory, json_path)
                    # Rebuild system if config has changed
                    if config_updated:
                        rebuild_nixos()
                        with open(json_path, "w") as f:
                            f.write(json.dumps(latest_config))
                else:
                    print('Request failed, status: ', config_response.status_code)
                    print(config_response.content)   
            except requests.exceptions.RequestException as e:
                print(e)

            # Reset last_checked and empty the lists
            cpu_usage_list = []
            mem_usage_list = []
            last_checked = time.time()

        precision = 1 # (seconds) Increase to trade performance for metric precision
        time.sleep(precision)

def process_config(raw_json_studio, state_directory, json_path):
    # 1 Check if config has changed since last rebuild
    config_path = state_directory+"/config.nix"
    if not os.path.isfile(json_path):
        with open(json_path, "w") as f:
            last_config = "{}"
            f.write(last_config)
            print("Created empty config at", json_path)
    else:
        with open(json_path, "r") as f:
            last_config = json.load(f)

    if last_config == raw_json_studio:
        return False # Same config as last update.

    # 2 Update config by constructing configuration from the new json
    new_sys_config = "{ config, pkgs, ... }:\n{"
    if "services" in raw_json_studio:
        print("Ran using api v0.2")
        for module_config in raw_json_studio:
            # config_type eg. services, users or networking
            print(raw_json_studio[module_config]) # services
            new_sys_config += module_config + " = {\n"
            for submodule in raw_json_studio[module_config]:
                print("______________")
                if "nixName" in submodule.keys():
                    print("Parsing nix config for", submodule["nixName"])
                    new_sys_config += parse_nix_json(submodule)
                else:
                    print("No nixName found in:", submodule)

            new_sys_config += "};"
    else: # Otherwise assume all items are services (v0.1)
        print("Ran using api v0.1")
        for module in raw_json_studio:
            module_config = "\n  services." + str(module["nixName"]) + " = {\n  "
            for option in module["options"]:
                module_config += "  " + str(option["nixName"]) + " = " + parse_nix_primitive(option["type"], option["value"]) + ";\n  "
            new_sys_config += module_config + "};"
    new_sys_config += "\n}"
    print(new_sys_config)

    # 3 Write the new config to the .nix file
    with open(config_path, "w") as f:
        f.write(new_sys_config)
    return True

def parse_nix_json(json_nix):
    # Recursively construct the nix expression working through each nixName and options
    """ 
    Sample Json 
    * UI-related fields removed
    * Includes the level higher than will be passed into this function, only the list is passed into this function
    {
        "services" : [{
        "nixName": "minecraft-server",
        "options": [
            {
            "nixName": "eula",
            "type": "boolean",
            "value": "true"
            },
            {
            "nixName": "declarative",
            "type": "boolean",
            "value": "true"
            }
        }]
    }
    In this example 'services' is the top-level config_type and each nixName under is a valid service module.

    Sample Nix:
        users.users."xnode".openssh.authorizedKeys = [ ssh-ed25519 AAAA...];
        networking.firewall.enable = true;
        services.openssh.enable = true;    
    """
    # If we are in a list (eg. services or options) parse each item
    print(type(json_nix))
    if isinstance(json_nix, list):
        nix_in_progress = ""
        for item in json_nix:
            print("ITEM:", item["nixName"])
            nix_in_progress += parse_nix_json(item)
            print("CURRENT IN PROGRESS:", nix_in_progress)
            print("-----------------------------------")

        return nix_in_progress

    elif isinstance(json_nix, dict):
        # A nix module with options, valid syntax: "minecraft-server = {options...};"
        if ("nixName" in json_nix.keys()) and ("options" in json_nix.keys()):
            #print("Found nixName and options in:", json_nix)
            return json_nix["nixName"] + " = {\n" + parse_nix_json(json_nix["options"]) + "};\n"

        # An option with a value
        if ("value" in json_nix.keys()) and ("options" not in json_nix.keys()):
            #print("Found value in:", json_nix)
            return json_nix["nixName"] + " = " + parse_nix_primitive(json_nix["type"], json_nix["value"]) + ";\n"

    else:
        print("Invalid input:", json_nix)
        print("Cannot be type: ", type(json_nix))
        return ""

def parse_nix_primitive(type, value): # Update for all optionTypes.txt  https://github.com/Openmesh-Network/NixScraper/blob/main/optionTypes.txt
    if type == "int":
        return value
    elif type == "float":
        return float(value)
    elif type.startswith("/") or type.startswith("./"):
        return value
    elif "string" in type:
        return '"' + value + '"'
    elif "raw" in type:
        return value
    else:
        return value

def calculate_metrics(cpu_usage_list, mem_usage_list):
    total = 0
    highest_cpu_usage = 0
    for i in cpu_usage_list:
        if i > highest_cpu_usage:
            highest_cpu_usage = i
        total += i

    avg_cpu_usage = total / len(cpu_usage_list)

    total = 0
    highest_mem_usage = 0
    for i in mem_usage_list:
        if i > highest_mem_usage:
            highest_mem_usage = i
        total += i

    avg_mem_usage = total / len(mem_usage_list)
    return avg_cpu_usage, avg_mem_usage, highest_cpu_usage, highest_mem_usage

def fetch_config_git():
    # To-do: Modularise the main function for readability
    pass

if __name__ == "__main__":
    main()
