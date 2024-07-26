import sys
import git
import hmac
import json
import argparse

def parse_cmd_args():
    parser = argparse.ArgumentParser(description="Xnode Admin service daemon that manages XnodeOS from the Xnode Studio.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("state_directory", help="Directory to store the xnode's configuration in", type=str, default="/var/lib/openmesh-xnode-admin")
    parser.add_argument("--remote", help="Either an Xnode functions API (see dpl backend) or a git remote.", type=str)
    parser.add_argument("--interval", help="How often to pull the git remote in seconds.", type=int, default=45)
    parser.add_argument("--proc", help="Either an Xnode functions api (see dpl backend) or a git remote.", type=str, default="/proc/cmdline")
    parser.add_argument("--no-proc", help="Don't read extra arguments from /proc/cmdline.", action="store_true")
    parser.add_argument("--uuid", help="The XnodeOS uuid, used for the Xnode functions API.", type=str)
    parser.add_argument("--access-token", help="The Xnode functions api access token, used to authenticate.", type=str)
    parser.add_argument("--git-mode", help="Use git-based configuration instead of the Xnode functions API.", action="store_true")
    parser.add_argument("--git-key", help="Optional git key used to verify commit signatures.", type=str)
    parser.add_argument("--key-type", help="Type of key (ssh or gpg) used for git commit verification", type=str, default="ssh-ed25519")

    return parser.parse_args()

def parse_all_args():
    # Get program arguments
    args = parse_cmd_args()
    if args.no_proc:
        # Don't take any extra arguments
        return args
    else:
        # Read extra arguments from /proc/cmdline
        print("Reading extra arguments from", args.proc)
        with open(args.proc, 'r') as cmdline:
            kernel_parameters = cmdline.read().split(" ")

            for param in kernel_parameters:
                if param.startswith("XNODE_UUID="):
                    args.uuid = param.split('XNODE_UUID=')[1]

                if param.startswith("XNODE_ACCESS_TOKEN="):
                    args.access_token = param.split('XNODE_ACCESS_TOKEN=')[1]

                if param.startswith("XNODE_CONFIG_REMOTE="):
                    args.remote = param.split('XNODE_CONFIG_REMOTE=')[1]
    return args

def parse_nix_json(json_nix):
    # Recursively construct the nix expression working through each nixName and it's options
    """ 
    Sample Json 
    * UI-related fields removed
    * Includes the level higher than will be passed into this function, only the list is passed into this function
    {
        "services" : [
            {
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
            }
        ]
    }
    In this example 'services' is the top-level config_type and each nixName under is a valid service module.
    The above json evaluates to:
        services = {
            minecraft-server = {
                eula = true;
                declarative = true;
            }
        }
    """
    # If we are in a list (eg. services or options) parse each item recursively
    print(type(json_nix))
    if isinstance(json_nix, list):
        nix_in_progress = ""
        for item in json_nix:
            nix_in_progress += parse_nix_json(item)
        return nix_in_progress

    elif isinstance(json_nix, dict):
        # A nix module with options, valid syntax: "minecraft-server = {options...};"
        if ("nixName" in json_nix.keys()) and ("options" in json_nix.keys()):
            return "  " + json_nix["nixName"] + " = {\n" + parse_nix_json(json_nix["options"]) + "  };\n"

        # An option with a value
        if ("value" in json_nix.keys()) and ("options" not in json_nix.keys()):
            return "    " + json_nix["nixName"] + " = " + parse_nix_primitive(json_nix["type"], json_nix["value"]) + ";\n"

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
    elif "string" == type:
        return '"' + value + '"'
    elif "raw" in type:
        return value
    elif "list of string" == type:
        # Assume strings inside of the list of already quoted
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

def configure_keys(user_key, use_ssh, repo):
    # Configure the commit signing key for a git repo.
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

def generate_hmac(access_token, message):
    msg_hmac_hex = ""

    if isinstance(message, dict):
        print("generating hmac for dict")
        json_str = json.dumps(message).replace(", ", ",").replace(": ", ":")
    else:
        json_str = message
    if isinstance(access_token, str): # Assumes hex if string
        msg_hmac_hex = hmac.new(bytes.fromhex(access_token), msg = bytes(json_str, 'utf-8'), digestmod='sha256').hexdigest()
    elif isinstance(access_token, bytes):
        msg_hmac_hex = hmac.new(access_token, msg = bytes(json_str, 'utf-8'), digestmod='sha256').hexdigest()
    else:
        print("Failed to generate HMAC:", access_token)
    print("Generated HMAC", msg_hmac_hex, "for message:", json_str)
    return msg_hmac_hex

