import json
import os
import psutil
import requests
import time
import shutil
import subprocess
from xnode_admin.utils import calculate_metrics, parse_nix_json, configure_keys, generate_hmac
import base64


def status_send(studio_url, xnode_uuid, preshared_key, status: str):
    # Send configuring status to DPL.
    status_message = {
        "id": str(xnode_uuid),
        "status": str(status),
    }
    status_hmac = generate_hmac(preshared_key, status_message)
    status_headers = {
        'x-parse-session-token': status_hmac
    }

    # Try to send a status to the studio, then pull the config.
    try:
        status_response = requests.post(studio_url + '/pushXnodeStatus', headers=status_headers, json=status_message)
        if not status_response.ok:
            print('Error sending status to dpl')
            print(status_response.content)
        else:
            print('Succesfully sent status to the dpl.')
    except requests.exceptions.RequestException as e:
        print(e)

def heartbeat_send(studio_url, xnode_uuid, preshared_key, cpu_usage_list, mem_usage_list, wants_update: bool):
    # Calculate metrics (average and maximum).
    avg_cpu_usage, avg_mem_usage, highest_cpu_usage, highest_mem_usage = calculate_metrics(cpu_usage_list, mem_usage_list)

    disk = psutil.disk_usage('/') # Only gets disk usage from root.
    heartbeat_message = {
        "id": str(xnode_uuid),
        "cpuPercent": (avg_cpu_usage),
        "cpuPercentPeek": (highest_cpu_usage),
        "ramMbUsed": (avg_mem_usage),
        "ramMbPeek": (highest_mem_usage),
        "ramMbTotal": (psutil.virtual_memory().total / (1024 * 1024)),

        "storageMbUsed":  (disk.used / (1024 * 1024)),
        "storageMbTotal": (disk.total / (1024 * 1024)),
    }

    if wants_update:
        heartbeat_message["wantUpdate"] = True

    heartbeat_hmac = generate_hmac(preshared_key, heartbeat_message)
    heartbeat_headers = {
        'x-parse-session-token': heartbeat_hmac
    }

    # Try to send a heartbeat to the studio, then pull the config.
    try:
        heartbeat_response = requests.post(studio_url + '/pushXnodeHeartbeat', headers=heartbeat_headers, json=heartbeat_message)
        if not heartbeat_response.ok:
            print('Failed to send heartbeat, response code not OK: ')
            print(heartbeat_response.content)
        else:
            print("Succesfully sent heartbeat.")
    except requests.exceptions.RequestException as e:
        print('Failed to send heartbeat, some kind of request exception occured: ')
        print(e)

# Gets the configuration from the dpl, also checks hmac for integrity.
def config_get(studio_url, xnode_uuid, preshared_key):
    get_config_message = {
        "id": str(xnode_uuid),
    }
    get_config_hmac = generate_hmac(preshared_key, get_config_message)
    get_config_headers = {
        'x-parse-session-token': get_config_hmac
    }

    print('Fetching update message at', time.time())

    try:
        config_response = requests.get(studio_url + '/getXnodeServices', headers=get_config_headers, json=get_config_message)

        if config_response.ok:

            config = config_response.json()

            if "message" in config.keys() and "hmac" in config.keys():
                message = config["message"]
                message_computed_hmac = generate_hmac(preshared_key, message)
                if message_computed_hmac == config["hmac"]:
                    print("HMAC of configuration verified")
                    parsed_message = json.loads(message)

                    if parsed_message["expiry"] > time.time()*1000:
                        base64_config = parsed_message["xnode_config"]
                        parsed_config = json.loads(base64.decodebytes(base64_config.encode('utf-8')))

                        return parsed_config
                    else:
                        print("Configuration expiry has passed.")
                        return None
                else:
                    print("HMAC of configuration not verified:", message_computed_hmac, "against claimed:", config["hmac"])
                    return None
        else:
            print('Config response failed!')
            print(config_response.content)
            return None
    except Exception as e:
        print('Couldn\'t get config response, reason: ')
        print(e)
        return None

# Returns true on the first case and the current generation on the other.
# Returns map with "configWant", "configHave", "updateWant", "updateHave":
def check_generation(studio_url, xnode_uuid, preshared_key):
    check_generation_message = {
        "id": str(xnode_uuid),
    }
    check_update_hmac = generate_hmac(preshared_key, check_generation_message)
    check_generation_headers = {
        'x-parse-session-token': check_update_hmac
    }

    try:
        check_update_response = requests.post(studio_url + '/getXnodeGeneration', headers=check_generation_headers, json=check_generation_message)
        if check_update_response.ok:
            content = check_update_response.json()

            if "configWant" in content and "configHave" in content and "updateWant" in content and "updateHave" in content:
                print("Got the generation values.")
                return content
            else:
                print("Generation not in expected format! Is the admin service out of date?")
                return None
        else:
            print('Error in check update request')
            print(check_update_response)
            return None
    except Exception as e:
        print('Failed to check update.')
        print(e)
        return None

def push_generation(studio_url, xnode_uuid, preshared_key, generation: int, is_config: bool):
    push_message = {
        "id": str(xnode_uuid),
        "generation": int(generation)
    }
    push_hmac = generate_hmac(preshared_key, push_message)
    push_headers = {
        'x-parse-session-token': push_hmac
    }

    try:
        endpoint = ""
        if (is_config):
            endpoint = "/pushXnodeGenerationConfig"
        else:
            endpoint = "/pushXnodeGenerationUpdate"

        push_response = requests.post(studio_url + endpoint, headers=push_headers, json=push_message)
        if not push_response.ok:
            print('Failed to push generation request to dpl.')
            print(push_response.content)
            return False
        else:
            return True
    except Exception as e:
        print('Failed to push generation.')
        print(e)
        return False

def fetch_config_studio(studio_url, xnode_uuid, access_token, state_directory):

    # Push a heartbeat with metrics to the studio and pull a configuration.
    hearbeat_interval = 30 # Heartbeat interval in seconds.
    generation_interval = 10 # API call to dpl to check if there's a new config or a new update.
    # XXX: Increase this interval to once every few hours, because it blocks for ~30 seconds in the best case.
    update_check_interval = 60 * 60 * 8 # How often to check if there's an update on the current channel.
    cpu_usage_list = []
    mem_usage_list = []
    preshared_key = base64.b64decode(access_token).hex()
    generation_timer = time.time() - generation_interval # Start by checking generation.
    heartbeat_timer = time.time() + hearbeat_interval
    update_check_timer = time.time() + update_check_interval

    wants_update = False

    # Send initial heartbeat and status to notify dpl.
    cpu_usage_list.append(psutil.cpu_percent())
    mem_usage_list.append(psutil.virtual_memory().used / (1024 * 1024))


    # XXX: This might cause problems.
    print('Initial rebuild...')
    successful_first_build = os_rebuild()
    print('Done with initial rebuild')

    if successful_first_build:
        print("Rebuilt succesfully.")
    else:
        print("First rebuild failed.")

    heartbeat_send(studio_url, xnode_uuid, preshared_key, cpu_usage_list, mem_usage_list, False)
    status_send(studio_url, xnode_uuid, preshared_key, "online")

    print('Starting main loop.')
    while True:
        # Collect metrics.
        cpu_usage_list.append(psutil.cpu_percent())
        mem_usage_list.append(psutil.virtual_memory().used / (1024 * 1024))

        # Check for changes in generation values. If they're mismatched, we have to reconfigure the system.
        if generation_timer + generation_interval < time.time():
            generation_data = check_generation(studio_url, xnode_uuid, preshared_key)

            if generation_data != None:

                configWant = int(generation_data["configWant"])
                configHave = int(generation_data["configHave"])
                updateWant = int(generation_data["updateWant"])
                updateHave = int(generation_data["updateHave"])

                if updateWant > updateHave:
                    print('Update want and have don\'t match, updating system.')

                    print('Sending push update request to dpl.')
                    success = push_generation(studio_url, xnode_uuid, preshared_key, updateHave + 1, False)

                    if not success:
                        print('Failed to push update.')
                    else:
                        wants_update = False
                        heartbeat_send(studio_url, xnode_uuid, preshared_key, cpu_usage_list, mem_usage_list, wants_update)

                        print('Updating machine...')
                        status_send(studio_url, xnode_uuid, preshared_key, "updating")

                        # WARN: Might restart this program at this point!
                        if os_update():
                            print('Succesfully updated machine!')
                        else:
                            print('This should never run there might be an issue with the code!')
                            print('Failed to apply update to machine.')

                        status_send(studio_url, xnode_uuid, preshared_key, "online")
                if configWant > configHave:
                    print('Config want and have don\'t match, must reconfigure.')
                    config = config_get(studio_url, xnode_uuid, preshared_key)

                    if config != None:
                        process_studio_config(config, state_directory)

                        print("Sending configuring status")
                        status_send(studio_url, xnode_uuid, preshared_key, "configuring")
                        success = push_generation(studio_url, xnode_uuid, preshared_key, configHave + 1, True)

                        # WARN: This could restart the machine.
                        rebuild_success = os_rebuild()

                        if rebuild_success:
                            print("Configuration succeeded. Sending online status.")
                            status_send(studio_url, xnode_uuid, preshared_key, "online")
                        else:
                            print("Configuration failed. Reverting!")
                            status_send(studio_url, xnode_uuid, preshared_key, "online")
                    else:
                        print('Couldn\'t fetch valid configuration from dpl.')
            else:
                print('No generation data, is the dpl down or is the admin service out of date?')

            generation_timer = time.time()

        if heartbeat_timer + hearbeat_interval < time.time():
            print('Sending heartbeat.')

            heartbeat_send(studio_url, xnode_uuid, preshared_key, cpu_usage_list, mem_usage_list, wants_update)

            heartbeat_timer = time.time()

            # Reset these lists, don't want to run out of memory.
            cpu_usage_list = []
            mem_usage_list = []

        # Only check for updates if we know we don't already have any updates queued up.
        if (update_check_timer + update_check_interval < time.time()) and not wants_update:
            print('Checking for updates...')

            status_send(studio_url, xnode_uuid, preshared_key, "checking updates")
            if os_update_check():
                print('Update found.')

                # Heartbeat should now include wants update flag.
                wants_update = True

                heartbeat_send(studio_url, xnode_uuid, preshared_key, cpu_usage_list, mem_usage_list, wants_update)
                status_send(studio_url, xnode_uuid, preshared_key, "online")
            else:
                print('No updates.')
                status_send(studio_url, xnode_uuid, preshared_key, "online")

            update_check_timer = time.time()

        precision = 1 # (seconds) Increase to trade performance for metric precision.
        time.sleep(precision)

def process_studio_config(studio_json_config, state_directory):
    # 1 Get config path.
    config_path = state_directory+"/config.nix"

    print('Studio json config:')
    print(studio_json_config)

    # 2 Update config by constructing configuration from the new json
    new_sys_config = "{ config, pkgs, ... }:\n{\n  "
    for module_config in studio_json_config:
        # config_type eg. services, users or networking
        print(studio_json_config[module_config]) # services
        new_sys_config += module_config + " = {\n  "
        for submodule in studio_json_config[module_config]:
            print("______________")
            if "nixName" in submodule.keys():
                print("Parsing nix config for", submodule["nixName"])
                new_sys_config += parse_nix_json(submodule)
            else:
                print("No nixName found in:", submodule)

        new_sys_config += "};\n"
    new_sys_config += "\n}"
    print(new_sys_config)

    # 3 Write the new config to the .nix file
    with open(config_path, "w") as f:
        f.write(new_sys_config)


def os_channel(update_or_rollback: bool):
    # Update the channel.
    argument = ""
    if update_or_rollback:
        argument = "--update"
    else:
        argument = "--rollback"

    result = subprocess.run(['/run/current-system/sw/bin/nix-channel', argument], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print('Error when running channel command.')
        print(result.stderr)
        return False
    else:
        return True

def os_channel_update():
    return os_channel(True)

def os_channel_rollback():
    return os_channel(False)

def os_rebuild():
    print('Running rebuild')


    result = subprocess.run(['/run/current-system/sw/bin/nixos-rebuild', '--verbose', 'switch', '-I', 'nixos-config=/etc/nixos/configuration.nix', '-I', 'nixpkgs=/root/.nix-defexpr/channels/nixos'])

    if result.returncode == 0:
        print("Rebuilt succesfully, log:")
        print(result.stderr)

        # Clean garbage:
        print("Running gc:")
        result = subprocess.run(['/run/current-system/sw/bin/nix-store', '--gc'])
        print("Done with gc.")

        return True
    else:
        print("Rebuild failure, log:")
        print(result.stdout)
        print(result.stderr)
        return False


def os_update():
    print('Running update')

    # Run channel update.
    if not os_channel_update():
        return False

    # Just nixos rebuild.
    return os_rebuild()

def os_update_check() -> bool:
    print('Updating channel...')

    # Remove the /root/.cache/nix directory
    # Otherwise Nix will just cache the tar file and not redownload it!
    try:
        print('Deleting Nix cache directory...')
        shutil.rmtree("/root/.cache/nix")
        print('Success! Or no exceptions at least.')
    except Exception as e:
        print('Failed to delete directory. Error: ')
        print(e)

    # Update the channel.
    if not os_channel_update():
        return False

    # Run build.
    print('Running build...')
    result = subprocess.run(['/run/current-system/sw/bin/nixos-rebuild', '-I', 'nixos-config=/etc/nixos/configuration.nix', '-I', 'nixpkgs=/root/.nix-defexpr/channels/nixos', 'build'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print('Error when running build command after channel update.')
        print(result.stderr)
        return False

    # Diff the build to see if there's a new version.
    print('Diffing build...')
    result = subprocess.run(['/run/current-system/sw/bin/nix', 'store', 'diff-closures', './result', '/run/current-system'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print('Error when running diff command after build on update check.')
        print(result.stderr)

    if len(result.stdout) > 0:
        print('Difference between new and current version, must be an update!')
        print('Changes: ')
        print(result.stdout)
        print('Changes in hex: ')
        print(result.stdout.hex())

        # There is a diff, so there's an update available.
        print('Rolling back changes in case the user wants to do a rebuild without updating.')
        os_channel_rollback()

        return True
    else:
        print('No difference between \"updated\" and current version')
        print(result.stdout)

        # No diff, therefore there isn't an update available
        return False

