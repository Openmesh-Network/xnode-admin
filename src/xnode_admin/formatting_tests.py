from nix_rebuilder import parse_nix_json
import json

with open("mock_studio_message.json", "r") as f:
    mock_data =  f.read()
mock_json = json.loads(mock_data)
print("______________XXXXXX_______________\n", mock_json["services"], "\n______________XXXXXX_______________")

def test():
    final_format = "{"
    for module_type in mock_json:
        print(module_type + "SERVICES SERVICES SERVICES SERVICES SERVICES ")
        final_format += module_type + " = {\n"
        final_format += parse_nix_json(mock_json[module_type], "")
        final_format += "};\n"

    final_format += "}"    
    print("----------------- FINAL FORM -----------------")
    print(final_format)
#test()

def api_v2(raw_json_studio):
    new_sys_config = "{ config, pkgs, ... }:\n{"
    if "services" in raw_json_studio:
        print("Ran using api v0.2")
        for config_type in raw_json_studio:
            # config_type eg. services, users or networking
            print(raw_json_studio[config_type]) # services
            for item in raw_json_studio[config_type]:
                print("______________")
                if "nixName" in item.keys():
                    print("Parsing nix config for", item["nixName"])
                    new_sys_config += parse_nix_json(item, new_sys_config)
                else:
                    print("No nixName found in:", item)

            #module_config = "\n" + config_type + str(config_type["nixName"]) + " = {\n  "
            #for option in config_type["Options"]:
            #    module_config += "  " + str(option["nixName"]) + " = " + parse_nix_primitive(option["type"], option["value"]) + ";\n  "
            new_sys_config += "};" #module_config + 
    return new_sys_config

#print(api_v2(mock_json))

my_test_json = {
    "services": [{
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
        ]
    },
    {
        "nixName": "minecraft-server2",
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
        ]
    },
    {
        "nixName": "minecraft-server3",
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
            },
            {
                "nixName": "serverProperties",
                "options":[
                    {
                        "nixName": "maxPlayers",
                        "type": "int",
                        "value": "555"
                    }
                ]
            }
        ]
    },
    ]
}
print(parse_nix_json(my_test_json["services"]))
#print(parse_nix_json(mock_json["services"]))
