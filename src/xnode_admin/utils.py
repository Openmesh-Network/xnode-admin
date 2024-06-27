import sys
import git
import hmac
import json

def parse_args():
    # Simple function to pass in arguments from the command line, argument order is important.
    opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    if len(args) >=3:
        print(sys.argv[1], sys.argv[2], sys.argv[3])
        # input validation for first 3 arguments (eg, int conversion, remote existence / reachability)
    else:
        print("Usage: xnode-rebuilder -[spgd] LOCAL_DIR REMOTE_CONFIG SEARCH_INTERVAL [USER_KEY] [POWERDNS_URL]")
        print("Git local and remote are required, user key can be SSH or GPG and powerdns is for scaling.")
        print("If using a USER_KEY please specify -s for SSH or -g for gpg.")
        sys.exit(1)

    user_key, key_type, userid = None, None, None

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
        
        if o.startswith("-p"): # Find uuid & psk at /proc/cmdline
            with open("/proc/cmdline") as file:
                kernel_params = file.read().split(" ")
                for kvar in kernel_params:
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
            powerdns_url = o.split("--powerdns=")[1] # Todo: Scalability + QoL with TXT records

    return args[0], args[1], int(args[2]), user_key, key_type, userid

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

def generate_hmac(access_token, message):
    if isinstance(message, dict):
        print("generating hmac for dict")
        json_str = json.dumps(message).replace(" ", "")
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

